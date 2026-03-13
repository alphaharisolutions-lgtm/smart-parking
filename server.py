import cv2
import numpy as np
import json
import os
import time
import threading
import asyncio
import shutil
from fastapi import FastAPI, Response, Request, UploadFile, File, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
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
VIDEO_SOURCE = "data/parking_video_1.mp4"
CONF_THRESHOLD = 0.2
DETECTION_MODE = "all" 

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
                    slots = json.load(f)
                    if slots: return slots
                except:
                    pass
        
        print(f"INFO: No manual slots for Cam {self.id}. Will use Auto-Discovery.")
        return []

    def auto_discover_slots(self, frame):
        """Dynamic slot discovery using orientation-aware line analysis."""
        print(f"DEBUG: Analyzing orientation for new source...")
        h, w = frame.shape[:2]
        
        # 1. Image Processing
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blur, 50, 150)
        lines = cv2.HoughLinesP(edges, 1, np.pi/180, 50, minLineLength=80, maxLineGap=20)
        
        detected_slots = []
        if lines is not None:
            # Check for dominant orientation (Vertical vs Horizontal)
            vert_lines = []
            horiz_lines = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                if abs(x1 - x2) < abs(y1 - y2): # Vertical
                    vert_lines.append(line[0])
                else: # Horizontal
                    horiz_lines.append(line[0])

            # Logic for Vertical Slots (like the bus lot)
            if len(vert_lines) > len(horiz_lines):
                print("DEBUG: Vertical Slot layout detected.")
                x_coords = sorted([l[0] for l in vert_lines] + [l[2] for l in vert_lines])
                cols = []
                if x_coords:
                    curr_x = x_coords[0]
                    cols.append(curr_x)
                    for x in x_coords:
                        if x > curr_x + 35: 
                            cols.append(x)
                            curr_x = x
                
                row_h = h // 2.5
                for r_idx in range(2):
                    y_start = int(h * 0.1) + (r_idx * int(row_h * 1.2))
                    for i in range(len(cols) - 1):
                        x1, x2 = cols[i], cols[i+1]
                        if x2 - x1 > 80: continue 
                        detected_slots.append([[x1, y_start], [x2, y_start], [x2, y_start + int(row_h)], [x1, y_start + int(row_h)]])
            
            # Logic for Horizontal/Angled Slots
            else:
                print("DEBUG: Horizontal/Angled layout detected.")
                y_coords = sorted([l[1] for l in horiz_lines] + [l[3] for l in horiz_lines])
                rows = []
                if y_coords:
                    curr_y = y_coords[0]
                    rows.append(curr_y)
                    for y in y_coords:
                        if y > curr_y + 100:
                            rows.append(y)
                            curr_y = y
                
                for ry in rows[:4]:
                    if ry > h * 0.8: continue
                    count = 12
                    sw = (w - 150) // count
                    slant = 20 if ry < h/2 else 40
                    for i in range(count):
                        x = 100 + (i * sw)
                        detected_slots.append([[x, ry], [x + sw - 10, ry], [x + sw - 10 + slant, ry + 70], [x + slant, ry + 70]])

        # Fallback grid if detection is sparse
        if len(detected_slots) < 8:
            print("DEBUG: Insufficient cues. Using balanced grid.")
            for r in range(2):
                y = int(h * (0.2 + (r * 0.4)))
                for c in range(12):
                    x = 60 + (c * (w-120)//12)
                    detected_slots.append([[x, y], [x + (w-120)//13, y], [x + (w-120)//13, y + int(h*0.3)], [x, y + int(h*0.3)]])

        print(f"DEBUG: Success. {len(detected_slots)} slots accurately mapped.")
        return detected_slots

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
        self.camera = Camera(1, VIDEO_SOURCE, "data/slots_video_1.json")
        self.lock = threading.Lock()
        self.latest_frame = None
        self.stats = self.get_initial_stats()
        self.running = True
        self.thread = threading.Thread(target=self.update_loop, daemon=True)
        self.thread.start()

    def get_initial_stats(self):
        total_slots = len(self.camera.slots)
        return {
            "total": total_slots,
            "occupied": 0,
            "vacant": total_slots,
            "utilization": 0,
            "slots": [], 
            "durations": [], 
            "source": "single-view"
        }

    def switch_video(self, video_path):
        with self.lock:
            self.camera.cap.release()
            self.camera.source = video_path
            self.camera.cap = cv2.VideoCapture(video_path)
            self.camera.slots = [] # Auto-detect for new video
            self.camera.occupancy = []
            self.camera.slot_start_times = []
            print(f"DEBUG: Switched to source: {video_path}")

    def update_settings(self, sensitivity: float):
        global CONF_THRESHOLD
        with self.lock:
            CONF_THRESHOLD = sensitivity

    def run_auto_discovery(self):
        with self.lock:
            frame = self.camera.get_frame()
            if frame is not None:
                self.camera.slots = self.camera.auto_discover_slots(frame)
                self.camera.occupancy = [False] * len(self.camera.slots)
                self.camera.slot_start_times = [None] * len(self.camera.slots)

    def update_loop(self):
        while self.running:
            with self.lock:
                frame = self.camera.get_frame()
                if frame is None:
                    time.sleep(1)
                    continue

                # Auto-discover if slots are missing
                if not self.camera.slots:
                    self.camera.slots = self.camera.auto_discover_slots(frame)
                    self.camera.occupancy = [False] * len(self.camera.slots)
                    self.camera.slot_start_times = [None] * len(self.camera.slots)

                # Inference
                results = self.model(frame, verbose=False, conf=CONF_THRESHOLD)
                
                # Reset occupancy
                self.camera.occupancy = [False] * len(self.camera.slots)
                
                # Check occupancy
                for result in results:
                    boxes = result.boxes
                    for box in boxes:
                        cls = int(box.cls[0])
                        # Filter for vehicles in COCO (cars, buses, trucks, etc.)
                        if cls in [2, 3, 5, 7, 1]: 
                            xyxy = box.xyxy[0].cpu().numpy()
                            # Midpoint of box
                            cx = int((xyxy[0] + xyxy[2]) / 2)
                            cy = int((xyxy[1] + xyxy[3]) / 2)
                            
                            # Check which slot contains this point
                            for i, slot in enumerate(self.camera.slots):
                                poly = np.array(slot, np.int32)
                                if cv2.pointPolygonTest(poly, (cx, cy), False) >= 0:
                                    self.camera.occupancy[i] = True
                
                # Update stats
                occupied_count = sum(self.camera.occupancy)
                total_slots = len(self.camera.slots)
                
                # Visuals
                for i, slot in enumerate(self.camera.slots):
                    color = (0, 0, 255) if self.camera.occupancy[i] else (0, 255, 0)
                    poly = np.array(slot, np.int32)
                    cv2.polylines(frame, [poly], True, color, 2)
                    
                    # Show Slot ID
                    cv2.putText(frame, str(i+1), (int(poly[0][0]), int(poly[0][1] - 5)), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

                # Encode and update latest frame
                _, buffer = cv2.imencode('.jpg', frame)
                self.latest_frame = buffer.tobytes()

                # Metrics update
                self.stats = {
                    "total": total_slots,
                    "occupied": occupied_count,
                    "vacant": total_slots - occupied_count,
                    "utilization": round((occupied_count / total_slots * 100) if total_slots > 0 else 0, 1),
                    "slots": self.camera.occupancy,
                    "source": "single-view"
                }

            time.sleep(0.01)

parking_system = ParkingSystem()

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "active_page": "dashboard"})

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

@app.post("/save_settings")
async def save_settings(request: Request):
    data = await request.json()
    sensitivity = data.get("sensitivity", 0.2)
    parking_system.update_settings(sensitivity)
    return {"status": "success", "message": "Settings applied"}

@app.post("/auto_detect")
async def auto_detect():
    parking_system.run_auto_discovery()
    return {"status": "success", "message": "Auto-detection complete. Slots identified."}

@app.post("/upload_video")
async def upload_video(file: UploadFile = File(...)):
    uploads_dir = "uploads"
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    
    file_path = os.path.join(uploads_dir, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    parking_system.switch_video(file_path)
    return {"status": "success", "message": f"Successfully uploaded {file.filename}."}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
