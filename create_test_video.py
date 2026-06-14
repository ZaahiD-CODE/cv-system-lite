import cv2
import numpy as np

fourcc = cv2.VideoWriter_fourcc(*'XVID')
out = cv2.VideoWriter('/root/cv_system/test_input.avi', fourcc, 25.0, (640, 480))

np.random.seed(42)
for i in range(150):
    frame = np.random.randint(30, 100, (480, 640, 3), dtype=np.uint8)
    
    x = int(100 + 300 * np.sin(i * 0.05))
    y = int(200 + 50 * np.cos(i * 0.1))
    cv2.rectangle(frame, (x, y), (x+80, y+120), (0, 255, 0), -1)
    cv2.putText(frame, "person", (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    x2 = int(400 - 200 * np.sin(i * 0.03))
    y2 = int(150 + 100 * np.cos(i * 0.07))
    cv2.rectangle(frame, (x2, y2), (x2+120, y2+60), (255, 0, 0), -1)
    cv2.putText(frame, "car", (x2, y2-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    
    cv2.putText(frame, f"Frame {i}/150", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
    
    out.write(frame)

out.release()
print("Test video created: test_input.avi (150 frames)")
