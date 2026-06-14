import cv2
import numpy as np
from typing import Optional, Tuple
from abc import ABC, abstractmethod


class BaseSource(ABC):
    def __init__(self):
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_opened = False

    @abstractmethod
    def open(self) -> bool:
        pass

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        if not self.is_opened or self.cap is None:
            return False, None
        ret, frame = self.cap.read()
        return ret, frame

    def release(self):
        if self.cap is not None:
            self.cap.release()
        self.is_opened = False

    def get_property(self, prop_id: int) -> float:
        if self.cap is not None:
            return self.cap.get(prop_id)
        return 0.0

    def get_fps(self) -> float:
        return self.get_property(cv2.CAP_PROP_FPS)

    def get_width(self) -> int:
        return int(self.get_property(cv2.CAP_PROP_FRAME_WIDTH))

    def get_height(self) -> int:
        return int(self.get_property(cv2.CAP_PROP_FRAME_HEIGHT))

    def get_frame_count(self) -> int:
        return int(self.get_property(cv2.CAP_PROP_FRAME_COUNT))

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
