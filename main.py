import subprocess
import time
import cv2
import os
import mysql.connector
from datetime import datetime
from typing import Optional, Dict

# Add GPIO import
import RPi.GPIO as GPIO

try:
    from picamera2 import Picamera2  
except:
    print("Error: 'picamera2' module not found. Install it using: ")
    print("sudo apt install python3-picamera2")
    exit(1)

try:
    from src.detect_vehicle import VehicleDetector
    from src.recognize_plate import PlateRecognizer
    from src.detect_plate import PlateDetector
    from src.open_dashboard import open_dashboard
except ImportError as e:
    raise ImportError(f"Required module not found: {e}")

class VehicleTracker:
    def __init__(self, capture_folder: str = "static/captured_vehicles", db_config: Optional[Dict] = None):
        self.vehicle_detector = VehicleDetector()
        self.plate_detector = PlateDetector()
        self.plate_recognizer = PlateRecognizer()
        
        self.capture_folder = capture_folder
        os.makedirs(self.capture_folder, exist_ok=True)

        self.cleanup_old_images(days=5)
        self.detected_vehicles: Dict[str, Dict] = {}
        
        self.db_config = db_config or {
            'host': 'localhost',
            'user': 'root',
            'password': "priyanshu",
            'database': 'vehicle_tracking'
        }
        self.db_connection = None
        self.db_cursor = None
        self.setup_database()

        # Setup GPIO for two LEDs
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        self.WHITELIST_LED_PIN = 18  # LED for whitelist matches
        self.DB_LED_PIN = 15        # LED for database saves
        GPIO.setup(self.WHITELIST_LED_PIN, GPIO.OUT)
        GPIO.setup(self.DB_LED_PIN, GPIO.OUT)
        GPIO.output(self.WHITELIST_LED_PIN, GPIO.LOW)
        GPIO.output(self.DB_LED_PIN, GPIO.LOW)

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
        
    def check_existing_plate(self, plate_number: str) -> Optional[Dict]:
        """Check if plate number exists in database and return its details."""
        if not self.db_connection or not self.db_cursor:
            print("Database connection not available")
            return None
        
        try:
            query = """
            SELECT plate_number, vehicle_type, confidence, capture_path
            FROM detected_vehicles
            WHERE plate_number = %s
            ORDER BY detection_time DESC
            LIMIT 1
            """
            self.db_cursor.execute(query, (plate_number,))
            result = self.db_cursor.fetchone()
            if result:
                return {
                    'plate_number': result[0],
                    'vehicle_type': result[1],
                    'confidence': result[2],
                    'capture_path': result[3]
                }
            return None
        except mysql.connector.Error as err:
            print(f"Error querying database: {err}")
            return None

    def delete_existing_entry(self, plate_number: str) -> bool:
        """Delete an existing entry and its capture file from the database and folder."""
        if not self.db_connection or not self.db_cursor:
            print("Database connection not available")
            return False
        
        try:
            # Get the capture path to delete the file
            existing = self.check_existing_plate(plate_number)
            if existing and existing['capture_path'] and os.path.exists(existing['capture_path']):
                os.remove(existing['capture_path'])
                print(f"Deleted old capture file: {existing['capture_path']}")
            
            # Delete from database
            delete_query = "DELETE FROM detected_vehicles WHERE plate_number = %s"
            self.db_cursor.execute(delete_query, (plate_number,))
            self.db_connection.commit()
            print(f"Deleted existing database entry for plate: {plate_number}")
            return True
        except mysql.connector.Error as err:
            print(f"Error deleting from database: {err}")
            self.db_connection.rollback()
            return False
        
    def check_whitelist(self, plate_number: str) -> bool:
        """Check if the plate number exists in the whitelist."""
        if not self.db_connection or not self.db_cursor:
            print("Database connection not available")
            return False
        
        try:
            normalized_plate_number = self.normalize_plate_number(plate_number)
            query = "SELECT COUNT(*) FROM whitelist_vehicles WHERE plate_number = %s"
            self.db_cursor.execute(query, (normalized_plate_number,))
            count = self.db_cursor.fetchone()[0]
            return count > 0
        except mysql.connector.Error as err:
            print(f"Error checking whitelist: {err}")
            return False

    def turn_on_whitelist_led(self, duration: float = 5.0):
        """Turn on the whitelist LED for a specified duration."""
        GPIO.output(self.WHITELIST_LED_PIN, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(self.WHITELIST_LED_PIN, GPIO.LOW)

    def turn_on_db_led(self, duration: float = 5.0):
        """Turn on the database LED for a specified duration."""
        GPIO.output(self.DB_LED_PIN, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(self.DB_LED_PIN, GPIO.LOW)
    
    def process_frame(self, frame):
        """Process a single video frame for vehicle and plate detection"""
        try:
            vehicle_detections = self.vehicle_detector.detect(frame)
            if not vehicle_detections:
                return frame
            
            vehicle_detections.sort(key=lambda x: x[5], reverse=True)
            x1, y1, x2, y2, vehicle_type, vehicle_conf = vehicle_detections[0]
            
            if vehicle_conf > 0.7:
                vehicle_region = frame[y1:y2, x1:x2]
                plate_detections = self.plate_detector.detect_plate(vehicle_region)
                if not plate_detections:
                    return frame
                
                plate_detections.sort(key=lambda x: x[4], reverse=True)
                px1, py1, px2, py2, plate_conf = plate_detections[0]
                px1, py1 = x1 + px1, y1 + py1
                px2, py2 = x1 + px2, y1 + py2
                
                plate_region = frame[py1:py2, px1:px2]
                plate_number = self.plate_recognizer.extract_text(plate_region)
                
                if plate_number:
                    current_time = time.time()
                    normalized_plate_number = self.normalize_plate_number(plate_number)
                    
                    # Check whitelist status
                    in_whitelist = self.check_whitelist(normalized_plate_number)

                    # Turn on whitelist LED for 5 seconds if in whitelist
                    if in_whitelist:
                        print(f"Vehicle {normalized_plate_number} found in whitelist - Turning on Whitelist LED for 5 seconds")
                        self.turn_on_whitelist_led(5.0)

                    # Track vehicle in memory
                    if normalized_plate_number not in self.detected_vehicles:
                        self.detected_vehicles[normalized_plate_number] = {
                            'timestamp': current_time,
                            'confidence': vehicle_conf,
                            'vehicle_type': vehicle_type,
                            'capture_frame': frame.copy(),
                            'capture_path': None,
                            'original_plate': plate_number,
                            'saved_to_db': False
                        }
                    else:
                        previous_detection = self.detected_vehicles[normalized_plate_number]
                        time_since_last_detection = current_time - previous_detection['timestamp']
                        
                        if time_since_last_detection < 10:
                            if vehicle_conf > previous_detection['confidence']:
                                self.detected_vehicles[normalized_plate_number].update({
                                    'timestamp': current_time,
                                    'confidence': vehicle_conf,
                                    'vehicle_type': vehicle_type,
                                    'capture_frame': frame.copy(),
                                    'original_plate': plate_number
                                })
                        else:
                            # Save to DB and turn on DB LED if new entry
                            self.save_highest_confidence_detection(normalized_plate_number)
                            if self.detected_vehicles[normalized_plate_number].get('saved_to_db'):
                                print(f"New plate {normalized_plate_number} added to detected_vehicles database - Turning on DB LED for 5 seconds")
                                self.turn_on_db_led(5.0)
                            self.detected_vehicles[normalized_plate_number] = {
                                'timestamp': current_time,
                                'confidence': vehicle_conf,
                                'vehicle_type': vehicle_type,
                                'capture_frame': frame.copy(),
                                'capture_path': None,
                                'original_plate': plate_number,
                                'saved_to_db': False
                            }

                    # Annotate frame
                    display_text = f"{vehicle_type} - {normalized_plate_number} ({vehicle_conf:.2f})"
                    cv2.putText(frame, display_text, (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.rectangle(frame, (px1, py1), (px2, py2), (255, 0, 0), 2)
        
        except Exception as e:
            print(f"Error processing frame: {e}")
        
        return frame

    def save_highest_confidence_detection(self, plate_number):
        """Save the highest confidence detection, replacing lower-confidence entries."""
        if plate_number not in self.detected_vehicles:
            return
        
        detection_data = self.detected_vehicles[plate_number]
        normalized_plate_number = self.normalize_plate_number(plate_number)
        
        # Check if this plate already exists in the database
        existing_entry = self.check_existing_plate(normalized_plate_number)
        
        if existing_entry:
            # If new confidence is lower, ignore this detection
            if detection_data['confidence'] <= existing_entry['confidence']:
                print(f"Ignoring lower confidence detection for {normalized_plate_number}: "
                      f"{detection_data['confidence']} <= {existing_entry['confidence']}")
                return
            
            # If higher confidence, delete the old entry
            self.delete_existing_entry(normalized_plate_number)
        
        # Save the new detection
        frame_to_save = detection_data['capture_frame'].copy()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{normalized_plate_number}_{timestamp}.jpg"
        filepath = os.path.join(self.capture_folder, filename)
        
        if cv2.imwrite(filepath, frame_to_save):
            success = self.save_to_database(
                plate_number=normalized_plate_number,
                vehicle_type=detection_data['vehicle_type'],
                confidence=detection_data['confidence'],
                capture_path=filepath
            )
            if success:
                print(f"Saved highest confidence detection: {normalized_plate_number}")
                self.detected_vehicles[normalized_plate_number]['capture_path'] = filepath
                self.detected_vehicles[normalized_plate_number]['saved_to_db'] = True
            else:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"Removed {filepath} due to database save failure")

    def run_detection(self):
        """
        Capture video frames from USB camera and perform vehicle detection.
        """
        camera_index = 0
        cap = cv2.VideoCapture(camera_index)

        if not cap.isOpened():
            print("Error: Could not open camera.")
            exit(1)

        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
        cap.set(cv2.CAP_PROP_FPS, 60)

        print(f"Actual FPS: {cap.get(cv2.CAP_PROP_FPS)}")
        print("USB Camera initialized successfully. Press 'q' to quit")

        frame_count = 0
        process_every_n_frames = 3
        start_time = time.time()

        while True:
            ret, frame = cap.read()
            if ret and frame is not None:
                frame_count += 1
                if frame_count % process_every_n_frames == 0:
                    processed_frame = self.process_frame(frame)
                    if frame_count % 30 == 0:
                        elapsed = time.time() - start_time
                        fps = (frame_count / process_every_n_frames) / elapsed
                        print(f"FPS: {fps:.2f}")
                        start_time = time.time()
                        frame_count = 0
                else:
                    processed_frame = frame
                cv2.imshow("Vehicle Detection", processed_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            else:
                print("No frame captured or error reading frame.")
                break

        cap.release()
        cv2.destroyAllWindows()
        print("Resources released.")
    
    def _cleanup(self) -> None:
        """Clean up resources"""
        if self.db_connection and self.db_cursor:
            try:
                self.db_cursor.close()
                self.db_connection.close()
                print("Database connection closed")
            except mysql.connector.Error as e:
                print(f"Error closing database connection: {e}")
        GPIO.output(self.WHITELIST_LED_PIN, GPIO.LOW)
        GPIO.output(self.DB_LED_PIN, GPIO.LOW)
        GPIO.cleanup()
        print("GPIO resources cleaned up")

    def __del__(self):
        """Destructor to ensure cleanup"""
        self._cleanup()

def main():
    """Main execution function"""
    print("Starting Flask server...")
    flask_process = subprocess.Popen(["python", "app.py"])
    time.sleep(3)  # Give Flask server time to start
    print("Flask app started successfully!")
    
    # Open the dashboard in the browser
    open_dashboard()

    try:
        db_config = {
            'host': 'localhost',
            'user': 'root',
            'password': "priyanshu",
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