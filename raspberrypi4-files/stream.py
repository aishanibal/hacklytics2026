from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import cv2

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

camera = cv2.VideoCapture(0)
if not camera.isOpened():
    raise RunTimeError("Could not start camera")

@app.get("/get-frame")
def generate_frames():
    success, frame = camera.read()
    if not success:
        return {"error": "failed to capture"}
    ret, buffer = cv2.imencode('.jpg', frame)
    if not ret:
        return {"error": "Failed to encode"}
    frame_bytes = buffer.tobytes()    
    
    return Response(content=frame_bytes, media_type="image/jpeg")
    
@app.route('/video-feed')
def video_feed():
    return StreamingResponse(generate_frames(), media_type='multipart/x-mixed-replace; boundary=frame')


