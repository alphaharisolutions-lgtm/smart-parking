import cv2
import numpy as np
from ultralytics import YOLO
import json
import os

class ParkingDetector:
    def __init__(self, model_path='yolov8n.pt', slots_path='data/slots.json'):
        self.model = YOLO(model_path)
        self.slots_path = slots_path
        self.slots = []
        self.load_slots()
        
        # Classes for vehicles in COCO dataset
        # 2: car, 3: motorcycle, 5: bus, 7: truck
        self.vehicle_classes = [2, 3, 5, 7]

    def load_slots(self):
        if os.path.exists(self.slots_path):
            with open(self.slots_path, 'r') as f:
                self.slots = json.load(f)
            print(f"Loaded {len(self.slots)} slots.")
        else:
            print(f"Warning: Slots file {self.slots_path} not found.")

    def check_occupancy(self, frame, detections):
        occupancy = [False] * len(self.slots)
        
        for i, slot in enumerate(self.slots):
            slot_poly = np.array(slot, np.int32)
            
            for det in detections:
                # det is [x1, y1, x2, y2, conf, cls]
                x1, y1, x2, y2 = det[:4]
                center_x = (x1 + x2) / 2
                center_y = (y1 + y2) / 2
                
                # Check if center of vehicle is inside the slot polygon
                if cv2.pointPolygonTest(slot_poly, (center_x, center_y), False) >= 0:
                    occupancy[i] = True
                    break
        
        return occupancy

    def detect(self, video_path):
        cap = cv2.VideoCapture(video_path)
        
        while cap.isOpened():
            success, frame = cap.read()
            if not success:
                break
                
            results = self.model(frame, verbose=False)[0]
            detections = []
            
            for r in results.boxes.data.tolist():
                x1, y1, x2, y2, conf, cls = r
                if int(cls) in self.vehicle_classes and conf > 0.3:
                    detections.append([x1, y1, x2, y2, conf, cls])
            
            occupancy = self.check_occupancy(frame, detections)
            
            # Draw slots
            for i, slot in enumerate(self.slots):
                color = (0, 0, 255) if occupancy[i] else (0, 255, 0)
                slot_poly = np.array(slot, np.int32)
                cv2.polylines(frame, [slot_poly], True, color, 2)
                
                # Label
                status = "Occupied" if occupancy[i] else "Vacant"
                cv2.putText(frame, f"Slot {i+1}: {status}", 
                            (slot[0][0], slot[0][1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

            # Draw summary
            vacant_count = occupancy.count(False)
            total_slots = len(self.slots)
            cv2.putText(frame, f"Vacant: {vacant_count}/{total_slots}", 
                        (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            cv2.imshow("Smart Parking Detection", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # detector = ParkingDetector()
    # detector.detect("data/parking_video.mp4")
    pass
