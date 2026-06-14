import cv2
import time
from typing import Optional
from .base import BaseSource


class RTSPSource(BaseSource):
    def __init__(self, url: str, buffer_size: int = 1):
        super().__init__()
        self.url = url
        self.buffer_size = buffer_size
        self._reconnect_attempts = 3
        self._reconnect_delay = 2

    def open(self) -> bool:
        return self._connect()

    def _connect(self) -> bool:
        if self.cap is not None:
            self.cap.release()
        
        self.cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, self.buffer_size)
        self.is_opened = self.cap.isOpened()
        
        if not self.is_opened:
            print(f"Failed to connect to RTSP stream: {self.url}")
        
        return self.is_opened

    def read(self):
        if not self.is_opened or self.cap is None:
            return False, None
        
        ret, frame = self.cap.read()
        
        if not ret:
            for attempt in range(self._reconnect_attempts):
                time.sleep(self._reconnect_delay)
                if self._connect():
                    ret, frame = self.cap.read()
                    if ret:
                        return ret, frame
        
        return ret, frame
