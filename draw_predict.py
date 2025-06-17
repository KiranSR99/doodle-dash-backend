import cv2
import numpy as np
import base64
import requests

API_URL = "http://localhost:5000/api/predict"
CANVAS_SIZE = 800
DRAW_RADIUS = 10
WHITE = 255
BLACK = 0

canvas = np.ones((CANVAS_SIZE, CANVAS_SIZE), dtype="uint8") * WHITE
drawing = False

def send_to_api(canvas):
    # Encode canvas as PNG without any preprocessing
    _, buffer = cv2.imencode('.png', canvas)
    png_bytes = buffer.tobytes()

    img_base64 = base64.b64encode(png_bytes).decode('utf-8')

    response = requests.post(API_URL, json={"image": img_base64})
    if response.status_code == 200:
        predictions = response.json().get("predictions", [])
        print("\nTop Predictions:")
        for i, pred in enumerate(predictions, start=1):
            print(f"{i}. {pred['label']} ({pred['confidence']*100:.2f}%)")
    else:
        print("Error:", response.json().get("error", "Unknown"))

def draw(event, x, y, flags, param):
    global drawing
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        cv2.circle(canvas, (x, y), DRAW_RADIUS, BLACK, -1)
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        cv2.circle(canvas, (x, y), DRAW_RADIUS, BLACK, -1)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        cv2.circle(canvas, (x, y), DRAW_RADIUS, BLACK, -1)

cv2.namedWindow("Draw")
cv2.setMouseCallback("Draw", draw)

print("""
🖌️ OpenCV Drawing Tool
- Draw with LEFT mouse button
- Press 'p' to predict
- Press 'c' to clear
- Press 'q' to quit
""")

while True:
    cv2.imshow("Draw", canvas)
    key = cv2.waitKey(1) & 0xFF
    if key == ord('p'):
        send_to_api(canvas)
    elif key == ord('c'):
        canvas.fill(WHITE)
        print("Canvas cleared.")
    elif key == ord('q'):
        break

cv2.destroyAllWindows()
