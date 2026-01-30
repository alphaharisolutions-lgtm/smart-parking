import argparse
import os
import sys
from src.selector import SlotSelector
from src.detector import ParkingDetector

def main():
    parser = argparse.ArgumentParser(description="Smart Parking Occupancy Detection System")
    parser.add_argument("--mode", type=str, choices=["select", "detect"], required=True,
                        help="Mode: 'select' to define slots, 'detect' to run occupancy detection")
    parser.add_argument("--video", type=str, default="data/parking_video.mp4",
                        help="Path to the video file or camera index")
    parser.add_argument("--slots", type=str, default="data/slots.json",
                        help="Path to save/load parking slots JSON")
    parser.add_argument("--model", type=str, default="yolov8n.pt",
                        help="YOLO model path")

    args = parser.parse_args()
    
    video_source = args.video
    if video_source.isdigit():
        video_source = int(video_source)

    if args.mode == "select":
        print(f"Starting Slot Selector for {video_source}...")
        selector = SlotSelector(video_source, args.slots)
        selector.run()
    elif args.mode == "detect":
        print(f"Starting Parking Detector on {video_source}...")
        detector = ParkingDetector(model_path=args.model, slots_path=args.slots)
        detector.detect(video_source)

if __name__ == "__main__":
    main()
