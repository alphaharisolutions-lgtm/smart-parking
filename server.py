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
class Camera:
    def __init__(self, id, source, slots_path):
        self.id = id
        self.source = source
        self.slots_path = slots_path
        self.cap = cv2.VideoCapture(source)
        self.slots = self.load_slots()
        self.slot_start_times = [None] * len(self.slots)
        self.occupancy = [False] * len(self.slots)

    def load_slots(self):
        if os.path.exists(self.slots_path):
            with open(self.slots_path, 'r') as f:
                try:
                    return json.load(f)
                except:
                    return []
        return []

    def get_frame(self):
        if self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                return self.get_frame()
            return frame
        return None

class ParkingSystem:
    def __init__(self):
        self.model = YOLO(MODEL_PATH)
        self.cameras = [
            Camera(1, "data/parking_video_1.mp4", "data/slots_video_1.json"),
            Camera(2, "data/parking_video_2.mp4", "data/slots_video_2.json")
        ]
        self.lock = threading.Lock()
        self.latest_frame = None
        self.stats = self.get_initial_stats()
        self.running = True
        self.thread = threading.Thread(target=self.update_loop, daemon=True)
        self.thread.start()

    def get_initial_stats(self):
        total_slots = sum(len(c.slots) for c in self.cameras)
        return {
            "total": total_slots,
            "occupied": 0,
            "vacant": total_slots,
            "utilization": 0,
            "slots": [],  # aggregated or list of lists? prefer flattened for stats
            "durations": [], 
            "source": "multi-view"
        }

    def update_settings(self, sensitivity: float):
        global CONF_THRESHOLD
        with self.lock:
            CONF_THRESHOLD = sensitivity
            print(f"DEBUG: System settings updated. Sensitivity: {sensitivity}")

    def update_loop(self):
        while self.running:
            frames = []
            
            # 1. Capture & Process Each Camera
            for cam in self.cameras:
                frame = cam.get_frame()
                if frame is None:
                    # Placeholder if cam fails
                    frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(frame, f"CAM {cam.id} LOST", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 2)
                
                # AI Inference
                try:
                    results = self.model(frame, verbose=False, conf=CONF_THRESHOLD)[0]
                    detections = []
                    for r in results.boxes.data.tolist():
                        if int(r[5]) in VEHICLE_IDS:
                            detections.append(r)
                except Exception as e:
                    print(f"DEBUG: AI Error Cam {cam.id}: {e}")
                    detections = []

                # Check Occupancy
                current_occupancy = [False] * len(cam.slots)
                for i, slot in enumerate(cam.slots):
                    poly = np.array(slot, np.int32)
                    for d in detections:
                        cx, cy = (d[0]+d[2])/2, (d[1]+d[3])/2
                        if cv2.pointPolygonTest(poly, (cx, cy), False) >= 0:
                            current_occupancy[i] = True
                            break
                    
                    # Update durations
                    if current_occupancy[i]:
                        if cam.slot_start_times[i] is None:
                            cam.slot_start_times[i] = time.time()
                    else:
                        cam.slot_start_times[i] = None
                
                cam.occupancy = current_occupancy

                # Visualization
                viz_frame = frame.copy()
                class_names = self.model.names
                
                # Draw Boxes
                for d in detections:
                    x1, y1, x2, y2 = map(int, d[:4])
                    conf = d[4]
                    cls_id = int(d[5])
                    label = f"{class_names[cls_id].upper()} {conf:.2f}"
                    cv2.rectangle(viz_frame, (x1, y1), (x2, y2), (255, 255, 0), 2)
                
                # Draw Slots
                for i, slot in enumerate(cam.slots):
                    is_occupied = current_occupancy[i]
                    color = (0, 0, 255) if is_occupied else (0, 255, 0)
                    cv2.polylines(viz_frame, [np.array(slot, np.int32)], True, color, 2)
                    
                    # Label Slot
                    M = cv2.moments(np.array(slot, np.int32))
                    if M["m00"] != 0:
                        cX = int(M["m10"] / M["m00"])
                        cY = int(M["m01"] / M["m00"])
                        cv2.putText(viz_frame, str(i+1), (cX-10, cY+5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

                frames.append(viz_frame)

            # 2. Stitch Frames (Two feeds side-by-side)
            if frames:
                # Resize to same height if needed
                h1, w1 = frames[0].shape[:2]
                h2, w2 = frames[1].shape[:2]
                
                target_h = min(h1, h2)
                if h1 != target_h:
                    frames[0] = cv2.resize(frames[0], (int(w1 * target_h / h1), target_h))
                if h2 != target_h:
                    frames[1] = cv2.resize(frames[1], (int(w2 * target_h / h2), target_h))
                
                combined_frame = np.hstack(frames)
                
                # Add titles
                cv2.putText(combined_frame, "CAM 1: VIEW A", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                cv2.putText(combined_frame, "CAM 2: VIEW B", (frames[0].shape[1] + 20, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

                _, buffer = cv2.imencode('.jpg', combined_frame)
                self.latest_frame = buffer.tobytes()

            # 3. Aggregate Stats
            total = sum(len(c.slots) for c in self.cameras)
            occupied = sum(sum(c.occupancy) for c in self.cameras)
            vacant = total - occupied
            utilization = (occupied / total * 100) if total > 0 else 0
            
            # Flattened durations for UI
            all_durations = []
            for cam in self.cameras:
                for t in cam.slot_start_times:
                   if t:
                       all_durations.append(f"{int((time.time()-t)/60)}m")
                   else:
                       all_durations.append("0m")
            
            self.stats = {
                "total": total,
                "occupied": occupied,
                "vacant": vacant,
                "utilization": utilization,
                "slots": [s for c in self.cameras for s in c.occupancy],
                "durations": all_durations,
                "source": "multi-view"
            }
            
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
    return {"status": "info", "message": "Source switching disabled in Multi-View mode"}

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
