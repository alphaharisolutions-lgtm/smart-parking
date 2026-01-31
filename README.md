# Alpha Parking: Smart Occupancy Detection System

Alpha Parking is a state-of-the-art parking management solution that leverages computer vision and deep learning to monitor parking slot occupancy in real-time. Built with **FastAPI** and **YOLOv8**, it provides a seamless web-based interface for monitoring, analytics, and system calibration.

## 🚀 Key Features

- **Real-Time AI Detection**: Uses YOLOv8s (You Only Look Once) for high-accuracy vehicle detection.
- **Multi-View Dashboard**: Interactive terminal showing live occupancy stats, trends, and slot logs.
- **Multiple Camera Support**: Seamlessly switch between video datasets and live webcam feeds.
- **Smart Analytics**: Track peak hours and historic occupancy performance.
- **Neural Calibration**: Adjust AI sensitivity, toggle Dark Mode, and configure system behavior in real-time.
- **Premium UI/UX**: Modern, responsive interface with a "Cyber-Light" aesthetic and glassmorphism elements.

## 🛠️ Tech Stack

- **Backend**: Python 3.8+, FastAPI, Uvicorn (Asynchronous Server)
- **AI/CV Engine**: Ultralytics YOLOv8s, OpenCV, NumPy
- **Frontend**: HTML5, Vanilla CSS3 (Custom Design System), JavaScript (ES6+)
- **Visualization**: Chart.js (Real-time occupancy trends)
- **Icons**: Font Awesome 6.4

## 📦 Project Structure

```text
├── data/               # Video datasets and slot definition JSONs
├── static/             # CSS styling and Frontend logic (JS)
├── templates/          # Jinja2 HTML templates
├── src/                # Core AI logic (Detector & Selector)
├── server.py           # Main Web Server entry point
├── main.py             # CLI entry point for slot selection/detection
└── requirements.txt    # Python dependencies
```

## ⚙️ Installation & Setup

Ensure you have Python 3.8 or higher installed on your system.

### 1. Clone the Project
```bash
git clone https://github.com/your-repo/smart-parking.git
cd smart-parking
```

### 2. Install Dependencies
It is recommended to use a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. (Optional) Run Slot Selector
If you want to define new parking slots for a specific video file or a **live camera**:

**For Video:**
```bash
python main.py --mode select --video data/parking_video_2.mp4 --slots data/slots_video.json
```

**For Live Camera (Webcam):**
```bash
# Use index 0 for internal webcam, or 1, 2 for external cameras
python main.py --mode select --video 0 --slots data/slots_webcam.json
```

**Selector Controls:**
- **Left Click**: Mark the 4 corners of a parking slot (Clockwise or Counter-clockwise).
- **'r'**: Reset current points if you made a mistake.
- **'q'**: Save all defined slots and exit the selector.

## 🖥️ Running the Application

To start the web-based dashboard:
```bash
python server.py
```
After the server starts, navigate to `http://localhost:8000` in your web browser.

> **Note:** If you encounter a `[Errno 10048]` error, it means port 8000 is already in use. Close any previous server instances or change the port in `server.py`.

## 🧠 System Configuration

The system is highly configurable via the **Settings** panel in the web UI:
- **AI Sensitivity**: Adjust the confidence threshold for YOLO detections (0.1 - 0.9).
- **Dark Mode**: Toggle between high-contrast light and dark themes.
- **Source Priority**: Choose the default camera/video source on startup.

## 📄 License
This project is developed for educational and research purposes in parking space occupancy detection using YOLO and multiple-view analysis.

---
**Developed by Alpha Vision Team**
