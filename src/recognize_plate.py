import cv2
from paddleocr import PaddleOCR
import imutils
import numpy as np

class PlateRecognizer:
    def __init__(self):
        """
        Initialize PaddleOCR with Indian English and custom configuration for license plates
        """
        self.ocr = PaddleOCR(
            use_angle_cls=True,  # Detect and correct text orientation
            lang='en',  # English language detection
            show_log=False  # Disable verbose logging
        )
    
    def preprocess_plate(self, plate_image):
        """
        Preprocess the plate image to improve OCR accuracy
        
        Args:
            plate_image (numpy.ndarray): Input plate image
        
        Returns:
            numpy.ndarray: Preprocessed plate image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(plate_image, cv2.COLOR_BGR2GRAY)
        
        # Apply adaptive thresholding
        thresh = cv2.adaptiveThreshold(
            gray, 255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 2
        )
        
        # Denoise
        denoised = cv2.fastNlMeansDenoising(thresh)
        
        # Resize for better OCR
        resized = cv2.resize(denoised, (0, 0), fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
        
        return resized
    
    def extract_text(self, plate_image, max_attempts=3):
        """
        Extract text from a license plate image using PaddleOCR, handling multi-line plates
        
        Args:
            plate_image (numpy.ndarray): Input plate image
            max_attempts (int): Maximum number of preprocessing attempts
        
        Returns:
            str: Processed license plate text or None if not detected
        """
        if plate_image is None or plate_image.size == 0:
            return None
        
        # Attempt multiple preprocessing techniques
        for attempt in range(max_attempts):
            try:
                # Apply different preprocessing based on attempt
                if attempt == 0:
                    # Original image
                    processed_image = plate_image
                elif attempt == 1:
                    # Preprocess with adaptive thresholding
                    processed_image = self.preprocess_plate(plate_image)
                else:
                    # Try rotating the image
                    processed_image = imutils.rotate_bound(plate_image, angle=5 * attempt)
                
                # Perform OCR detection
                results = self.ocr.ocr(processed_image, cls=True)
                
                # Process and filter results
                if results and results[0] is not None:
                    # Collect detected text with their bounding box coordinates
                    detected_texts_with_coords = []
                    for line in results[0]:
                        if line is None:
                            continue
                        # line[0] contains the bounding box coordinates: [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
                        # line[1] contains the text and confidence: (text, confidence)
                        text, confidence = line[1]
                        if confidence > 0.7:  # High confidence threshold
                            # Get the top-left y-coordinate for sorting (line[0][0][1] is y1)
                            y_coord = line[0][0][1]
                            detected_texts_with_coords.append((y_coord, text.replace(" ", "").upper()))
                    
                    # Sort by y-coordinate to ensure top-to-bottom order
                    detected_texts_with_coords.sort(key=lambda x: x[0])
                    
                    # Combine all detected texts into a single string
                    if detected_texts_with_coords:
                        # Join the texts (you can add a separator if needed, e.g., a space or newline)
                        combined_text = "".join(text for _, text in detected_texts_with_coords)
                        return combined_text
            
            except Exception as e:
                print(f"OCR attempt {attempt + 1} failed: {e}")
        
        return None