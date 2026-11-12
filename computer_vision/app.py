import cv2
from ultralytics import YOLO

# 1. Load the lightweight YOLO26 Nano model
model = YOLO('yolo26n.pt')

# 2. Open the Nikon camera feed (Index 1 or 2 via Nikon Webcam Utility)
cap = cv2.VideoCapture(1)

if not cap.isOpened():
    print("Error: Could not access the camera stream.")
    exit()

print("Press 'q' in the video window to safely exit.")

while True:
    ret, frame = cap.read()
    if not ret:
        print("Failed to capture image frame from video feed.")
        break

    # Run streaming inference to optimize laptop memory
    results = model(frame, stream=True)

    for r in results:
        annotated_frame = r.plot()

    # Open a local native display window
    cv2.imshow("Surf Cam - YOLO26 Live Feed", annotated_frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
