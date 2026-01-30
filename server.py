import cv2
import numpy as np
import json
import os
import time
import threading
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
MODEL_PATH = "yolov8n.pt"
SLOTS_PATH = "data/slots.json"
VIDEO_SOURCE = "data/parking_video_1.mp4"
CONF_THRESHOLD = 0.3

# Global State
class ParkingSystem:
    def __init__(self):
        self.model = YOLO(MODEL_PATH)
        self.slots = self.load_slots()
        self.cap = cv2.VideoCapture(VIDEO_SOURCE)
        self.latest_frame = None
        self.stats = {
            "total": len(self.slots),
            "occupied": 0,
            "vacant": 0,
            "utilization": 0,
            "slots": [],
            "durations": []
        }
        self.slot_start_times = [None] * len(self.slots)
        self.vehicle_ids = [2, 3, 5, 7] # car, motorcycle, bus, truck
        self.running = True
        self.thread = threading.Thread(target=self.update_loop, daemon=True)
        self.thread.start()

    def load_slots(self):
        if os.path.exists(SLOTS_PATH):
            with open(SLOTS_PATH, 'r') as f:
                return json.load(f)
        return []

    def update_loop(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            # AI Inference
            results = self.model(frame, verbose=False, conf=CONF_THRESHOLD)[0]
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
                "durations": durations
            }

            # Visualization
            viz_frame = frame.copy()
            for i, slot in enumerate(self.slots):
                is_occupied = current_occupancy[i]
                color = (75, 75, 255) if is_occupied else (127, 255, 0) # BGR
                alpha = 0.3 if is_occupied else 0.15
                
                overlay = viz_frame.copy()
                cv2.fillPoly(overlay, [np.array(slot, np.int32)], color)
                cv2.addWeighted(overlay, alpha, viz_frame, 1 - alpha, 0, viz_frame)
                cv2.polylines(viz_frame, [np.array(slot, np.int32)], True, color, 2)
                
                M = cv2.moments(np.array(slot, np.int32))
                if M["m00"] != 0:
                    cX = int(M["m10"] / M["m00"])
                    cY = int(M["m01"] / M["m00"])
                    cv2.putText(viz_frame, str(i+1), (cX-10, cY+5), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

            _, buffer = cv2.imencode('.jpg', viz_frame)
            self.latest_frame = buffer.tobytes()
            
            time.sleep(0.01)

parking_system = ParkingSystem()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/video_feed")
async def video_feed():
    def gen():
        while True:
            if parking_system.latest_frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + parking_system.latest_frame + b'\r\n')
            time.sleep(0.05)
    return StreamingResponse(gen(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.get("/stats")
async def get_stats():
    return parking_system.stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
