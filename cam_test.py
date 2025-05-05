import cv2

# Initialize the USB camera
# Camera index 0 is typically the first USB camera
camera_index = 0
cap = cv2.VideoCapture(camera_index)

# Check if camera opened successfully
if not cap.isOpened():
    print("Error: Could not open camera.")
    exit()

# Set resolution (optional)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

print("Press 'q' to quit")

# Main loop to capture and display frames
while True:
    # Read frame from camera
    ret, frame = cap.read()
    
    # Check if frame was read successfully
    if not ret:
        print("Error: Can't receive frame (stream end?). Exiting ...")
        break
    
    # Display the frame
    cv2.imshow('USB Camera Test', frame)
    
    # Exit on 'q' key press
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release the camera and close windows
cap.release()
cv2.destroyAllWindows()