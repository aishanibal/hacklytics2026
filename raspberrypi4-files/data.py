from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
import cv2
import asyncio
import json
from fastapi.responses import StreamingResponse, JSONResponse
import uvicorn
from ble_config import scan
from bleak import BleakScanner

app = FastAPI()

cap = cv2.VideoCapture(1)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 880)
cap.set(cv2.CAP_PROP_FPS, 15)

@app.route('/video-stream')
async def video(request):
    async def frame_stream():
        while True:
            ret, frame = cap.read()
            if not ret:
                await asyncio.sleep(0.01)
                continue
            
            _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            
            yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n'
            
            await asyncio.sleep(0.01)
        
    try:
        return StreamingResponse(frame_stream(), media_type='multipart/x-mixed-replace; boundary=frame')
    except Exception as e:
        return {"error": str(e)}

@app.route('/health')
async def health(request):
    return {"status": "ok", "camera": capisOpened()}


@app.get('/ble-data')
async def ble_data():
    try:
        devices = await scan()
        return {"devices": devices}
    except Exception as e:
        return {"error": str(e)}
    
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
