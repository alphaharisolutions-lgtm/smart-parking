import cv2
import numpy as np
import json
import os
import time
import threading
import asyncio
from fastapi import FastAPI, Response, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse
from ultralytics import YOLO
from datetime import datetime

app = FastAPI()

# Mount static and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuration
MODEL_PATH = "yolov8s.pt"
VIDEO_SLOTS_PATH = "data/slots_video.json"
WEBCAM_SLOTS_PATH = "data/slots_webcam.json"
VIDEO_SOURCE = "data/parking_video_2.mp4"
CONF_THRESHOLD = 0.2
DETECTION_MODE = "all" # Options: "vehicles" or "all"
# Class 0 is 'person' in COCO. 
# We'll use a wide range of IDs or a flag to include everything.
VEHICLE_IDS = list(range(80)) if DETECTION_MODE == "all" else [2, 3, 5, 7, 1, 6, 8, 0] 

# Global State
class ParkingSystem:
    def __init__(self):
        self.model = YOLO(MODEL_PATH)
        self.source_type = "video"
        self.slots = self.load_slots(self.source_type)
        self.cap = cv2.VideoCapture(VIDEO_SOURCE)
        self.lock = threading.Lock()
        self.latest_frame = None
        self.stats = self.get_initial_stats()
        self.slot_start_times = [None] * len(self.slots)
        self.vehicle_ids = VEHICLE_IDS
        self.running = True
        self.thread = threading.Thread(target=self.update_loop, daemon=True)
        self.thread.start()

    def load_slots(self, source_type):
        path = VIDEO_SLOTS_PATH if source_type == "video" else WEBCAM_SLOTS_PATH
        # Fallback to data/slots.json if the specific file doesn't exist
        if not os.path.exists(path) and os.path.exists("data/slots.json"):
            print(f"DEBUG: {path} not found, falling back to data/slots.json")
            path = "data/slots.json"
            
        if os.path.exists(path):
            with open(path, 'r') as f:
                try:
                    return json.load(f)
                except:
                    return []
        return []

    def get_initial_stats(self):
        return {
            "total": len(self.slots),
            "occupied": 0,
            "vacant": len(self.slots),
            "utilization": 0,
            "slots": [False] * len(self.slots),
            "durations": ["0m"] * len(self.slots),
            "source": self.source_type
        }

    def switch_source(self, source_type: str):
        if source_type == self.source_type:
            return
        
        print(f"DEBUG: Receiving switch request to: {source_type}")
        new_cap = None
        
        # Initialize new capture outside the main lock
        if source_type == "webcam":
            print("DEBUG: Attempting to open Webcam (Index 0) using DSHOW...")
            new_cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not new_cap.isOpened():
                print("DEBUG: Index 0 failed, trying Index 1...")
                new_cap = cv2.VideoCapture(1, cv2.CAP_DSHOW)
        else:
            print("DEBUG: Loading video file...")
            new_cap = cv2.VideoCapture(VIDEO_SOURCE)

        # Swap the captures inside the lock
        with self.lock:
            if new_cap and new_cap.isOpened():
                if self.cap:
                    self.cap.release()
                self.cap = new_cap
                self.source_type = source_type
                
                # Update slots for the new source
                self.slots = self.load_slots(source_type)
                self.slot_start_times = [None] * len(self.slots)
                self.stats = self.get_initial_stats()
                
                print(f"SUCCESS: Switched to {source_type.upper()}. Slots updated to {len(self.slots)} items.")
            else:
                print(f"ERROR: Could not open {source_type}. Keeping current source.")
                if new_cap:
                    new_cap.release()

    def update_settings(self, sensitivity: float):
        global CONF_THRESHOLD
        with self.lock:
            CONF_THRESHOLD = sensitivity
            print(f"DEBUG: System settings updated. Sensitivity: {sensitivity}")

    def update_loop(self):
        while self.running:
            frame = None
            with self.lock:
                if self.cap and self.cap.isOpened():
                    try:
                        ret, frame = self.cap.read()
                        if not ret or frame is None:
                            if self.source_type == "video":
                                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                            else:
                                # For webcam, a failed read might be temporary
                                time.sleep(0.1)
                            continue
                    except Exception as e:
                        print(f"DEBUG: Error reading frame: {e}")
                        time.sleep(0.1)
                        continue

            if frame is None:
                time.sleep(0.1)
                continue

            # AI Inference
            try:
                results = self.model(frame, verbose=False, conf=CONF_THRESHOLD)[0]
            except Exception as e:
                print(f"DEBUG: AI Inference Error: {e}")
                time.sleep(0.1)
                continue
            detections = []
            for r in results.boxes.data.tolist():
                if int(r[5]) in self.vehicle_ids:
                    detections.append(r)

            current_occupancy = [False] * len(self.slots)
            for i, slot in enumerate(self.slots):
                poly = np.array(slot, np.int32)
                for d in detections:
                    cx, cy = (d[0]+d[2])/2, (d[1]+d[3])/2
                    if cv2.pointPolygonTest(poly, (cx, cy), False) >= 0:
                        current_occupancy[i] = True
                        break
                
                # Update durations
                if current_occupancy[i]:
                    if self.slot_start_times[i] is None:
                        self.slot_start_times[i] = time.time()
                else:
                    self.slot_start_times[i] = None

            # Calculate Stats
            occ_count = sum(current_occupancy)
            vac_count = len(self.slots) - occ_count
            util = (occ_count / len(self.slots) * 100) if self.slots else 0
            
            durations = []
            for t in self.slot_start_times:
                if t:
                    mins = int((time.time() - t) / 60)
                    durations.append(f"{mins}m")
                else:
                    durations.append("0m")

            self.stats = {
                "total": len(self.slots),
                "occupied": occ_count,
                "vacant": vac_count,
                "utilization": util,
                "slots": current_occupancy,
                "durations": durations,
                "source": self.source_type
            }

            # Visualization
            viz_frame = frame.copy()
            
            # Get class names from model
            class_names = self.model.names

            # Draw AI Detections (Debugging)
            for d in detections:
                x1, y1, x2, y2 = map(int, d[:4])
                conf = d[4]
                cls_id = int(d[5])
                label = f"{class_names[cls_id].upper()} {conf:.2f}"
                
                # Draw Box
                cv2.rectangle(viz_frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
                
                # Draw Label Background
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                cv2.rectangle(viz_frame, (x1, y1 - 20), (x1 + w, y1), (255, 255, 0), -1)
                cv2.putText(viz_frame, label, (x1, y1 - 5), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1)

            # Only draw slots if they exist
            for i, slot in enumerate(self.slots):
                is_occupied = current_occupancy[i]
                color = (75, 75, 255) if is_occupied else (127, 255, 0) # BGR
                alpha = 0.3 if is_occupied else 0.15
                
                overlay = viz_frame.copy()
                cv2.fillPoly(overlay, [np.array(slot, np.int32)], color)
                cv2.addWeighted(overlay, alpha, viz_frame, 1 - alpha, 0, viz_frame)
                cv2.polylines(viz_frame, [np.array(slot, np.int32)], True, color, 2)
                
                # Label Slot Status
                M = cv2.moments(np.array(slot, np.int32))
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    
                    # Slot Number
                    cv2.putText(viz_frame, str(i+1), (cX-10, cY+5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    
                    # Status Text below number
                    status_text = "OCCUPIED" if is_occupied else "VACANT"
                    cv2.putText(viz_frame, status_text, (cX-30, cY+25), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)


            _, buffer = cv2.imencode('.jpg', viz_frame)
            self.latest_frame = buffer.tobytes()
            
            time.sleep(0.01)

parking_system = ParkingSystem()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "active_page": "dashboard"})

@app.get("/feeds", response_class=HTMLResponse)
async def feeds(request: Request):
    return templates.TemplateResponse("feeds.html", {"request": request, "active_page": "feeds"})

@app.get("/analytics", response_class=HTMLResponse)
async def analytics(request: Request):
    return templates.TemplateResponse("analytics.html", {"request": request, "active_page": "analytics"})

@app.get("/settings", response_class=HTMLResponse)
async def settings(request: Request):
    return templates.TemplateResponse("settings.html", {"request": request, "active_page": "settings"})

@app.get("/video_feed")
async def video_feed():
    def gen():
        while True:
            if parking_system.latest_frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + parking_system.latest_frame + b'\r\n')
            time.sleep(0.04)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/stats")
async def get_stats():
    return parking_system.stats

@app.post("/switch_source")
async def switch_source(request: Request):
    data = await request.json()
    source = data.get("source", "video")
    parking_system.switch_source(source)
    return {"status": "success", "source": source}

@app.post("/save_settings")
async def save_settings(request: Request):
    data = await request.json()
    sensitivity = data.get("sensitivity", 0.2)
    # Applying settings to the live system
    parking_system.update_settings(sensitivity)
    return {"status": "success", "message": "Settings applied"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
