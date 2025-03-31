import subprocess
import time
import cv2
import os
import mysql.connector
from datetime import datetime
from typing import Optional, Dict
from dotenv import load_dotenv

load_dotenv()

try:
    from src.detect_vehicle import VehicleDetector
    from src.recognize_plate import PlateRecognizer
    # from src.fetch_vehicle_info import VehicleInfoFetcher
    from src.detect_plate import PlateDetector
except ImportError as e:
    raise ImportError(f"Required module not found: {e}")

class VehicleTracker:
    def __init__(self, capture_folder: str = "static\\captured_vehicles", db_config: Optional[Dict] = None):
        """
        Initialize Vehicle Tracking System
        
        Args:
            capture_folder (str): Directory to save captured vehicle images
            db_config (dict): MySQL database configuration
        """
        self.vehicle_detector = VehicleDetector()
        self.plate_detector = PlateDetector()
        self.plate_recognizer = PlateRecognizer()
        # self.vehicle_info_fetcher = VehicleInfoFetcher()
        
        self.capture_folder = capture_folder
        os.makedirs(self.capture_folder, exist_ok=True)

        self.cleanup_old_images(days=5)

        self.detected_vehicles: Dict[str, Dict] = {}
        
        self.db_config = db_config or {
            'host': 'localhost',
            'user': 'root',
            'password': os.getenv("password"),
            'database': 'vehicle_tracking'
        }
        self.db_connection = None
        self.db_cursor = None
        self.setup_database()

    def cleanup_old_images(self, days: int = 5):
        """Deletes images older than the specified number of days."""
        now = time.time()
        cutoff_time = now - (days * 86400)

        for filename in os.listdir(self.capture_folder):
            file_path = os.path.join(self.capture_folder, filename)
            if os.path.isfile(file_path):
                file_creation_time = os.path.getctime(file_path)
                if file_creation_time < cutoff_time:
                    os.remove(file_path)
                    print(f"Deleted old image: {filename}")
    
    def setup_database(self) -> None:
        """Set up database connection and create required tables"""
        try:
            self.db_connection = mysql.connector.connect(**self.db_config)
            self.db_cursor = self.db_connection.cursor()
            
            create_table_query = """
            CREATE TABLE IF NOT EXISTS detected_vehicles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                plate_number VARCHAR(20) NOT NULL,
                vehicle_type VARCHAR(20) NOT NULL,
                confidence FLOAT NOT NULL,
                capture_path VARCHAR(255),
                detection_time DATETIME NOT NULL
            )
            """
            create_table_query2 = """
            CREATE TABLE IF NOT EXISTS whitelist_vehicles (
                id INT AUTO_INCREMENT PRIMARY KEY,
                owner_name VARCHAR(60) NOT NULL,
                plate_number VARCHAR(20) NOT NULL,
                vehicle_type VARCHAR(20) NOT NULL
            );
            """
            self.db_cursor.execute(create_table_query)
            print("Created/verified 'detected_vehicles' table")
            self.db_cursor.execute(create_table_query2)
            print("Created/verified 'whitelist_vehicles' table")
            self.db_connection.commit()
            print("Database connection established and tables verified")
            
        except mysql.connector.Error as err:
            print(f"Database error: {err}")
            self.db_connection = None
            self.db_cursor = None

    def normalize_plate_number(self, plate_number: str) -> str:
        """Remove dots from the plate number."""
        return plate_number.replace(".", "")
    
    def save_to_database(self, plate_number: str, vehicle_type: str, confidence: float, 
                        capture_path: str) -> bool:
        """Save vehicle detection information to database"""
        if not self.db_connection or not self.db_cursor:
            print("Database connection not available")
            return False
        
        try:
            normalized_plate_number = self.normalize_plate_number(plate_number)

            insert_query = """
            INSERT INTO detected_vehicles 
            (plate_number, vehicle_type, confidence, capture_path, detection_time)
            VALUES (%s, %s, %s, %s, %s)
            """
            detection_time = datetime.now()
            
            self.db_cursor.execute(insert_query, (
                normalized_plate_number, vehicle_type, confidence, capture_path, detection_time
            ))
            self.db_connection.commit()
            print(f"Saved to database: Plate {normalized_plate_number}, Type {vehicle_type}, Path {capture_path}")
            return True
            
        except mysql.connector.Error as err:
            print(f"Error saving to database: {err}")
            self.db_connection.rollback()
            return False
    
    def test_database_connection(self) -> bool:
        """Test database connection by inserting a test record"""
        if not self.db_connection or not self.db_cursor:
            print("Database connection not available")
            return False
        else:
            return True
    
    def process_frame(self, frame):
        """Process a single video frame for vehicle and plate detection"""
        try:
            # Step 1: Detect vehicles
            vehicle_detections = self.vehicle_detector.detect(frame)
            if not vehicle_detections:
                return frame
            
            # Sort vehicle detections by confidence (highest first)
            vehicle_detections.sort(key=lambda x: x[5], reverse=True)
            x1, y1, x2, y2, vehicle_type, vehicle_conf = vehicle_detections[0]
            
            if vehicle_conf > 0.7:
                vehicle_region = frame[y1:y2, x1:x2]
                
                # Step 2: Detect license plate within vehicle region
                plate_detections = self.plate_detector.detect_plate(vehicle_region)
                if not plate_detections:
                    return frame
                
                # Take the highest-confidence plate detection
                plate_detections.sort(key=lambda x: x[4], reverse=True)
                px1, py1, px2, py2, plate_conf = plate_detections[0]
                
                # Adjust coordinates relative to original frame
                px1, py1 = x1 + px1, y1 + py1
                px2, py2 = x1 + px2, y1 + py2
                
                # Step 3: Extract plate region and recognize text
                plate_region = frame[py1:py2, px1:px2]
                plate_number = self.plate_recognizer.extract_text(plate_region)
                
                if plate_number:
                    current_time = time.time()
                    normalized_plate_number = self.normalize_plate_number(plate_number)
                    
                    # Initialize detection tracking if new vehicle
                    if normalized_plate_number not in self.detected_vehicles:
                        self.detected_vehicles[normalized_plate_number] = {
                            'timestamp': current_time,
                            'confidence': vehicle_conf,
                            'vehicle_type': vehicle_type,
                            'capture_frame': frame.copy(),
                            'capture_path': None,
                            'original_plate': plate_number  # Store original for reference
                        }
                    else:
                        # Check if new detection is within 10 seconds
                        previous_detection = self.detected_vehicles[normalized_plate_number]
                        time_since_last_detection = current_time - previous_detection['timestamp']
                        
                        if time_since_last_detection < 10:
                            # Only update if confidence is higher
                            if vehicle_conf > previous_detection['confidence']:
                                self.detected_vehicles[normalized_plate_number].update({
                                    'timestamp': current_time,
                                    'confidence': vehicle_conf,
                                    'vehicle_type': vehicle_type,
                                    'capture_frame': frame.copy(),
                                    'original_plate': plate_number
                                })
                        else:
                            # Save highest confidence detection after time threshold
                            self.save_highest_confidence_detection(normalized_plate_number)
                            # Reset tracking for this plate
                            self.detected_vehicles[normalized_plate_number] = {
                                'timestamp': current_time,
                                'confidence': vehicle_conf,
                                'vehicle_type': vehicle_type,
                                'capture_frame': frame.copy(),
                                'capture_path': None,
                                'original_plate': plate_number
                            }
                    
                    # Annotate the frame for display with normalized plate number
                    display_text = f"{vehicle_type} - {normalized_plate_number} ({vehicle_conf:.2f})"
                    cv2.putText(frame, display_text, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)  # Vehicle box
                    cv2.rectangle(frame, (px1, py1), (px2, py2), (255, 0, 0), 2)  # Plate box
        
        except Exception as e:
            print(f"Error processing frame: {e}")
        
        return frame

    def save_highest_confidence_detection(self, plate_number):
        """Save the highest confidence detection after the time threshold"""
        if plate_number in self.detected_vehicles:
            detection_data = self.detected_vehicles[plate_number]
            
            # Create a copy of the frame to draw bounding boxes for saving
            frame_to_save = detection_data['capture_frame'].copy()
            
            # Save capture with normalized plate number in filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{plate_number}_{timestamp}.jpg"  # Using normalized plate_number
            filepath = os.path.join(self.capture_folder, filename)
            
            if cv2.imwrite(filepath, frame_to_save):
                # self.vehicle_info_fetcher.get_vehicle_info(plate_number)
                
                # Save to database
                success = self.save_to_database(
                    plate_number=plate_number,  # Already normalized
                    vehicle_type=detection_data['vehicle_type'],
                    confidence=detection_data['confidence'],
                    capture_path=filepath
                )
                
                if success:
                    print(f"Saved highest confidence detection: {plate_number}")
                else:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        print(f"Removed {filepath} due to database save failure")

    def run_detection(self, video_source=0) -> None:
        """Run continuous video detection"""
        cap = cv2.VideoCapture(video_source)
        if not cap.isOpened():
            print(f"Error: Could not open video source {video_source}")
            return
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    print("End of video stream or error reading frame")
                    break
                
                processed_frame = self.process_frame(frame)
                cv2.imshow("Vehicle Detection", processed_frame)
                
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                
        except Exception as e:
            print(f"Error in detection loop: {e}")
        finally:
            cap.release()
            cv2.destroyAllWindows()
            self._cleanup()
    
    def _cleanup(self) -> None:
        """Clean up resources"""
        if self.db_connection and self.db_cursor:
            try:
                self.db_cursor.close()
                self.db_connection.close()
                print("Database connection closed")
            except mysql.connector.Error as e:
                print(f"Error closing database connection: {e}")
    
    def __del__(self):
        """Destructor to ensure cleanup"""
        self._cleanup()

def main():
    """Main execution function"""
    # Start Flask app.py in background
    print("Starting Flask server...")
    flask_process = subprocess.Popen(["python", "app.py"])
    time.sleep(3)  # Allow time for Flask to start
    print("Flask app started successfully!")

    try:
        db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': os.getenv("password"),
            'database': 'vehicle_tracking'
        }
        
        tracker = VehicleTracker(db_config=db_config)
        if tracker.test_database_connection():
            tracker.run_detection()
        else:
            print("Skipping detection due to database connection failure")
    
    except Exception as e:
        print(f"An error occurred in main: {e}")

    finally:
        print("Stopping Flask server...")
        flask_process.terminate()
        flask_process.wait()
        print("Flask app stopped.")

if __name__ == "__main__":
    main()