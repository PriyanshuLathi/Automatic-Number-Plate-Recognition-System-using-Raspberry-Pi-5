from ultralytics import YOLO

class PlateDetector:
    def __init__(self, model_path='models/best_license_float16.tflite'):
        """
        Initialize License Plate Detector with a YOLO model
        
        Args:
            model_path (str): Path to pre-trained YOLO model for plate detection
        """
        self.model = YOLO(model_path, task='detect')
    
    def detect_plate(self, frame):
        """
        Detect license plates in the input frame
        
        Args:
            frame (numpy.ndarray): Input image/frame
        
        Returns:
            list: Detected plate bounding boxes [x1, y1, x2, y2, confidence]
        """
        if frame is None:
            return []
        
        try:
            # Run inference
            results = self.model(frame)[0]
            plates = []
            
            # Process each detection
            for box in results.boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                
                if conf > 0.6:  # Confidence threshold for plates
                    plates.append([x1, y1, x2, y2, conf])
            
            return plates
        
        except Exception as e:
            print(f"Error in plate detection: {e}")
            return []