import cv2
from typing import Optional
from .base import BaseSource


class VideoSource(BaseSource):
    def __init__(self, source: str):
        super().__init__()
        self.source = source

    def open(self) -> bool:
        self.cap = cv2.VideoCapture(self.source)
        self.is_opened = self.cap.isOpened()
        return self.is_opened

    def get_frame_count(self) -> int:
        if self.cap is not None:
            return int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return 0

    def set_frame_position(self, frame_pos: int):
        if self.cap is not None:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
