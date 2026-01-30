import cv2

def check_cameras():
    print("Checking for available cameras...")
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret:
                print(f"✅ Camera Index {i} is WORKING.")
            else:
                print(f"⚠️ Camera Index {i} is detected but cannot read frames.")
            cap.release()
        else:
            print(f"❌ Camera Index {i} is NOT detected.")

if __name__ == "__main__":
    check_cameras()
