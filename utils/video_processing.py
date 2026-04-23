import cv2
from ultralytics import YOLO
import time
from datetime import datetime
import threading
import queue

class CrimeDetector:
    def __init__(self, model_path='yolov8n.pt'):
        print("Loading YOLOv8 model...")
        self.model = YOLO(model_path)
        self.alerts_queue = queue.Queue(maxsize=10)
        self.last_alert_time = 0
        self.alert_cooldown = 5 # Seconds between alerts
        
        # Define suspicious classes (COCO dataset indices)
        # 0: person (for overcrowding/general monitoring)
        # 43: knife
        # 76: scissors (simulated weapon)
        # We can also detect 'cell phone' (67) if we want to sim 'theft'
        self.suspicious_classes = {
            43: 'Knife Detected',
            76: 'Weapon Detected', 
            # Add more as needed. For demo, we might alert on 'person' if it's a restricted area
            # but usually we want specific threats.
        }

    def process_frame(self, frame):
        """
        Runs inference on a frame and draws bounding boxes.
        Returns processed frame and list of detections.
        """
        results = self.model(frame, verbose=False)
        annotated_frame = results[0].plot()
        
        detections = []
        current_time = time.time()
        
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                
                # Check for suspicious objects
                if cls in self.suspicious_classes and conf > 0.5:
                    label = self.suspicious_classes[cls]
                    detections.append(label)
                    
                    # Trigger Alert if cooldown passed
                    if current_time - self.last_alert_time > self.alert_cooldown:
                        self.trigger_alert(label)
                        self.last_alert_time = current_time
                        
        return annotated_frame, detections

    def trigger_alert(self, label):
        alert = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "message": f"ALERT: {label}",
            "severity": "High"
        }
        if not self.alerts_queue.full():
            self.alerts_queue.put(alert)
        print(f"!!! CRIME ALERT: {label} !!!")

    def get_latest_alerts(self):
        alerts = []
        while not self.alerts_queue.empty():
            alerts.append(self.alerts_queue.get())
        return alerts

# Global detector instance
detector = None

def get_detector():
    global detector
    if detector is None:
        detector = CrimeDetector()
    return detector

def generate_frames():
    """
    Generator for Flask video feed.
    Uses webcam (0) or a video file if provided.
    """
    det = get_detector()
    
    # Use 0 for webcam. 
    # If the user has a video file, we could use that path.
    # For now, we default to 0 (Webcam) for the "Live Feed" simulation.
    cap = cv2.VideoCapture(0) 
    
    if not cap.isOpened():
        print("Error: Could not open video source.")
        return

    while True:
        success, frame = cap.read()
        if not success:
            break
            
        # Process frame
        annotated_frame, _ = det.process_frame(frame)
        
        # Encode
        ret, buffer = cv2.imencode('.jpg', annotated_frame)
        frame_bytes = buffer.tobytes()
        
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

    cap.release()
