import cv2
import json
import os

class SlotSelector:
    def __init__(self, video_path, output_path):
        self.video_path = video_path
        self.output_path = output_path
        self.slots = []
        self.current_slot = []
        self.initialized = False
        
        # Determine if source is a file, camera index, or URL
        source = video_path
        if isinstance(video_path, str) and video_path.isdigit():
            source = int(video_path)
        elif isinstance(video_path, str) and (video_path.startswith("http://") or video_path.startswith("https://") or video_path.startswith("rtsp://")):
            source = video_path
        elif not isinstance(video_path, int) and not os.path.exists(video_path):
            print(f"Error: Video source {video_path} not found.")
            return

        self.cap = cv2.VideoCapture(source)
        self.initialized = False
        success, self.frame = self.cap.read()
        if not success:
            print(f"Error: Could not read from video source {video_path}. Make sure the camera is connected and not used by another app.")
            return

        self.initialized = True
        self.window_name = "Parking Slot Selector - Click 4 points per slot (Right click to reset current, 's' to save, 'q' to quit)"
        cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
        # Maximize the window automatically
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.setWindowProperty(self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL) # Toggle back to normal but maximized
        cv2.setMouseCallback(self.window_name, self.mouse_callback)

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.current_slot.append((x, y))
            if len(self.current_slot) == 4:
                self.slots.append(self.current_slot)
                self.current_slot = []
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.current_slot = []

    def run(self):
        if not self.initialized:
            print("Selector not initialized properly. Skipping run.")
            return
        while True:
            temp_frame = self.frame.copy()
            
            # Draw existing slots
            for slot in self.slots:
                for i in range(4):
                    cv2.line(temp_frame, slot[i], slot[(i+1)%4], (0, 255, 0), 2)
            
            # Draw current slot being defined
            for i in range(len(self.current_slot)):
                cv2.circle(temp_frame, self.current_slot[i], 5, (0, 0, 255), -1)
                if i > 0:
                    cv2.line(temp_frame, self.current_slot[i-1], self.current_slot[i], (0, 0, 255), 2)

            cv2.imshow(self.window_name, temp_frame)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('s'):
                with open(self.output_path, 'w') as f:
                    json.dump(self.slots, f)
                print(f"Saved {len(self.slots)} slots to {self.output_path}")
            elif key == ord('q'):
                break

        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # Example usage:
    # selector = SlotSelector("data/parking_video.mp4", "data/slots.json")
    # selector.run()
    pass
