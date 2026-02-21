import requests
import cv2
import numpy as np
import time

URL = "http://10.90.253.181:8000/get-frame"

while True:
    try: 
        response = requests.get(URL)
        if response.status_code == 200:
            img_arr = np.frombuffer(response.content, np.uint8)
            frame = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
            cv2.imshow("Frame", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        else:
            print("Failed to get frame")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(0.1)
cv2.destroyAllWindows()