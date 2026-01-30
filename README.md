# 🛡️ ALPHA | Smart Parking AI
A premium, AI-powered parking management system using YOLOv8 for real-time vehicle detection and occupancy monitoring.

## 🌟 Key Features
*   **AI Detection**: Real-time vehicle detection (Cars, Motorcycles, Buses, Trucks) using YOLOv8.
*   **FastAPI Dashboard**: A modern, high-performance web dashboard with real-time updates via streaming and WebSockets.
*   **Premium UI**: Custom-built dashboard with light theme aesthetics, smooth animations, and live analytics.
*   **Real-Time Analytics**: Live occupancy trends, utilization percentages, and detailed slot logs.
*   **Slot Mapping**: Interactive tool to define parking slots on any video feed.

---

## 🚀 How to Run

### 1. Prerequisites
Ensure you have the following installed:
*   **Python 3.8+**
*   **webcam** OR **video source**

### 2. Installation
Clone the project and install requirements:
```bash
# Install dependencies
pip install -r requirements.txt
```

### 3. Setup (Map Your Parking Slots)
If you are using a new video or camera, you need to mark the parking slots first:
```bash
python main.py --mode select --video data/parking_video_1.mp4
```
*   **Left Click**: Add points to create a polygon for a slot.
*   **Right Click**: Finish current slot.
*   **'q' or 'Esc'**: Save and exit.

### 4. Launch the Dashboard
Start the premium AI monitoring system:
```bash
# Run the FastAPI server
python server.py
```
View the dashboard at: `http://localhost:8000`

---

## 📁 Project Structure
*   `server.py`: The main FastAPI server and AI engine.
*   `static/`: Dashboard styles and scripts.
*   `templates/`: HTML templates for the dashboard.
*   `main.py`: CLI entry point for slot selection.
*   `src/detector.py`: Core AI logic using YOLOv8.
*   `src/selector.py`: Tool for manual slot mapping.
*   `data/slots.json`: Saved coordinates for your parking layout.

---

**Developed by ALPHA AI Systems**
