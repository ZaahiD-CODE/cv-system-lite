import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import time
import json
import asyncio
import threading
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from sqlalchemy.orm import Session
from collections import defaultdict

from web.database import init_db, get_db, User, Stream, Counter, DetectionEvent
from web.auth import get_password_hash, decode_token
from web.routers import auth_router, streams_router, users_router, training_router, stats_router, system_router

app = FastAPI(title="CV System", version="1.0.0")

ALLOWED_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(streams_router)
app.include_router(users_router)
app.include_router(training_router)
app.include_router(stats_router)
app.include_router(system_router)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))


@app.on_event("startup")
async def startup():
    init_db()
    from web.database import SessionLocal
    db = SessionLocal()
    try:
        admin_password = os.environ.get("CV_ADMIN_PASSWORD", "XCFqm22tYmzqCZUraP0E")
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@vlesssec.ru",
                hashed_password=get_password_hash(admin_password),
                role="admin"
            )
            db.add(admin)
            db.commit()
    finally:
        db.close()


def render(template_name: str, request: Request):
    return templates.TemplateResponse(request, template_name)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return render("login.html", request)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render("login.html", request)

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return render("dashboard.html", request)

@app.get("/streams", response_class=HTMLResponse)
async def streams_page(request: Request):
    return render("streams.html", request)

@app.get("/counters", response_class=HTMLResponse)
async def counters_page(request: Request):
    return render("counters.html", request)

@app.get("/users", response_class=HTMLResponse)
async def users_page(request: Request):
    return render("users.html", request)

@app.get("/training", response_class=HTMLResponse)
async def training_page(request: Request):
    return render("training.html", request)


@app.get("/system", response_class=HTMLResponse)
async def system_page(request: Request):
    return render("system.html", request)


class StreamManager:
    def __init__(self):
        self.captures: dict[int, cv2.VideoCapture] = {}
        self.latest_frames: dict[int, bytes] = {}
        self.lock = threading.Lock()

    def get_capture(self, stream_id: int) -> cv2.VideoCapture | None:
        if stream_id in self.captures and self.captures[stream_id].isOpened():
            return self.captures[stream_id]
        return None

    def open_stream(self, stream_id: int, source_type: str, source_path: str) -> bool:
        with self.lock:
            if stream_id in self.captures:
                self.captures[stream_id].release()

            if source_type == "camera":
                cap = cv2.VideoCapture(int(source_path))
            elif source_type == "rtsp":
                cap = cv2.VideoCapture(source_path, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            else:
                cap = cv2.VideoCapture(source_path)

            if cap.isOpened():
                self.captures[stream_id] = cap
                return True
            return False

    def release_stream(self, stream_id: int):
        with self.lock:
            if stream_id in self.captures:
                self.captures[stream_id].release()
                del self.captures[stream_id]
            self.latest_frames.pop(stream_id, None)

    def read_frame(self, stream_id: int):
        cap = self.get_capture(stream_id)
        if cap is None:
            return None
        ret, frame = cap.read()
        if not ret:
            return None
        return frame

    def get_snapshot(self, stream_id: int, source_type: str, source_path: str):
        cap = self.get_capture(stream_id)
        if cap is None:
            if not self.open_stream(stream_id, source_type, source_path):
                return None
            cap = self.get_capture(stream_id)
        ret, frame = cap.read()
        if not ret:
            return None
        return frame


stream_manager = StreamManager()


def generate_mjpeg(stream_id: int, source_type: str, source_path: str):
    if not stream_manager.open_stream(stream_id, source_type, source_path):
        error_frame = _make_error_frame("Нет сигнала")
        _, buf = cv2.imencode('.jpg', error_frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')
        return

    fps_limit = 15
    frame_interval = 1.0 / fps_limit

    while True:
        start = time.time()
        frame = stream_manager.read_frame(stream_id)
        if frame is None:
            frame = _make_error_frame("Потеря сигнала")
        else:
            h, w = frame.shape[:2]
            if w > 960:
                scale = 960 / w
                frame = cv2.resize(frame, (960, int(h * scale)))

        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buf.tobytes() + b'\r\n')

        elapsed = time.time() - start
        if elapsed < frame_interval:
            time.sleep(frame_interval - elapsed)


def _make_error_frame(text: str):
    import numpy as np
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    cv2.putText(frame, text, (180, 190), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (100, 100, 100), 2)
    return frame


@app.get("/api/stream/{stream_id}/mjpeg")
async def stream_mjpeg(stream_id: int):
    from web.database import SessionLocal
    db = SessionLocal()
    try:
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream:
            return HTMLResponse(status_code=404, content="Stream not found")
        source_type = stream.source_type
        source_path = stream.source_path
    finally:
        db.close()
    return StreamingResponse(
        generate_mjpeg(stream_id, source_type, source_path),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.get("/api/stream/{stream_id}/snapshot")
async def stream_snapshot(stream_id: int):
    from web.database import SessionLocal
    db = SessionLocal()
    try:
        stream = db.query(Stream).filter(Stream.id == stream_id).first()
        if not stream:
            return HTMLResponse(status_code=404, content="Stream not found")

        frame = stream_manager.get_snapshot(stream_id, stream.source_type, stream.source_path)
        if frame is None:
            return HTMLResponse(status_code=503, content="Cannot open stream")

        _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        from fastapi.responses import Response
        return Response(content=buf.tobytes(), media_type="image/jpeg")
    finally:
        db.close()


class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket

    def disconnect(self, client_id: str):
        self.active_connections.pop(client_id, None)

    async def send_message(self, message: str, client_id: str):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)


manager = ConnectionManager()


@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await manager.connect(websocket, client_id)
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            if message.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(client_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
