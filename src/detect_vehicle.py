from ultralytics import YOLO
import cv2

class VehicleDetector:
    def __init__(self, model_path='models/best_float16.tflite'):
        """
        Initialize Vehicle Detector with YOLOv8 model
        
        Args:
            model_path (str): Path to pre-trained YOLOv8 model
        """
        self.model = YOLO(model_path, task='detect')
        self.class_names = ["2-wheeler", "3-wheeler", "HMV", "LMV"]
    
    def detect(self, frame):
        """
        Detect vehicles in the input frame
        
        Args:
            frame (numpy.ndarray): Input image/frame
        
        Returns:
            list: Detected vehicle information [x1, y1, x2, y2, vehicle_type]
        """
        # Ensure frame is not empty
        if frame is None:
            return []
        
        try:
            # Run inference
            results = self.model(frame)[0]
            detections = []
            
            # Process each detection
            for box in results.boxes:
                # Extract bounding box coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                
                # Get confidence score
                conf = float(box.conf[0])
                
                # Get class ID
                class_id = int(box.cls[0])
                
                # Filter detections by confidence
                if conf > 0.5:
                    # Get vehicle type
                    vehicle_type = (self.class_names[class_id] 
                                    if class_id < len(self.class_names) 
                                    else "Unknown")
                    
                    # Add detection to list
                    detections.append([x1, y1, x2, y2, vehicle_type, conf])
            
            return detections
        
        except Exception as e:
            print(f"Error in vehicle detection: {e}")
            return []
    
    def draw_detections(self, frame, detections):
        """
        Draw bounding boxes and labels on the frame
        
        Args:
            frame (numpy.ndarray): Input image/frame
            detections (list): List of detections
        
        Returns:
            numpy.ndarray: Frame with detections drawn
        """
        # Create a copy of the frame to avoid modifying original
        output = frame.copy()
        
        for detection in detections:
            x1, y1, x2, y2, vehicle_type, conf = detection
            
            # Draw bounding box
            cv2.rectangle(output, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            # Draw label
            label = f"{vehicle_type} {conf:.2f}"
            cv2.putText(output, label, (x1, y1-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, 
                        (0, 255, 0), 2)
        
        return output