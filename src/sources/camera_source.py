import cv2
from typing import Optional
from .base import BaseSource


class CameraSource(BaseSource):
    def __init__(self, camera_id: int = 0):
        super().__init__()
        self.camera_id = camera_id

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.camera_id)
        self.is_opened = self.cap.isOpened()
        return self.is_opened

    def set_resolution(self, width: int, height: int):
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

    def set_fps(self, fps: int):
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_FPS, fps)
