import cv2
import torch
import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class Detection:
    bbox: Tuple[int, int, int, int]
    confidence: float
    class_id: int
    class_name: str


AVAILABLE_MODELS = {
    "yolo12n.pt":  {"name": "YOLO12 Nano",    "size": "~5MB",   "speed": "very_fast", "accuracy": "low"},
    "yolo12s.pt":  {"name": "YOLO12 Small",   "size": "~18MB",  "speed": "fast",      "accuracy": "medium"},
    "yolo12m.pt":  {"name": "YOLO12 Medium",  "size": "~39MB",  "speed": "medium",    "accuracy": "good"},
    "yolo12l.pt":  {"name": "YOLO12 Large",   "size": "~51MB",  "speed": "slow",      "accuracy": "high"},
    "yolo12x.pt":  {"name": "YOLO12 X-Large", "size": "~114MB", "speed": "very_slow", "accuracy": "very_high"},
}


def get_device() -> str:
    if torch.cuda.is_available():
        gpu_name = torch.cuda.get_device_name(0)
        gpu_mem = torch.cuda.get_device_properties(0).total_mem / 1024**3
        print(f"GPU detected: {gpu_name} ({gpu_mem:.1f} GB)")
        return "cuda:0"
    print("No GPU detected, using CPU")
    return "cpu"


def get_gpu_info() -> Optional[Dict[str, Any]]:
    if not torch.cuda.is_available():
        return None
    props = torch.cuda.get_device_properties(0)
    return {
        "name": torch.cuda.get_device_name(0),
        "memory_total_gb": round(props.total_mem / 1024**3, 1),
        "memory_used_gb": round(torch.cuda.memory_allocated(0) / 1024**3, 1),
        "memory_free_gb": round((props.total_mem - torch.cuda.memory_allocated(0)) / 1024**3, 1),
        "capability": f"{props.major}.{props.minor}",
    }


class Detector:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.model = None
        self.device = "cpu"
        self._load_model()

    def _load_model(self):
        from ultralytics import YOLO

        model_path = self.config.get("model", "yolo12n.pt")
        self.confidence = self.config.get("confidence", 0.5)
        self.input_size = self.config.get("input_size", 640)

        requested_device = self.config.get("device", "auto")
        if requested_device == "auto":
            self.device = get_device()
        else:
            self.device = requested_device

        self.model = YOLO(model_path)

        if self.device.startswith("cuda"):
            self.model.to(self.device)
            print(f"Model {model_path} loaded on {self.device}")
        else:
            print(f"Model {model_path} loaded on CPU")

    def detect(self, frame: np.ndarray) -> List[Detection]:
        results = self.model(
            frame,
            conf=self.confidence,
            device=self.device,
            imgsz=self.input_size,
            verbose=False
        )

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    cls_name = self.model.names[cls_id]
                    detections.append(Detection(
                        bbox=(x1, y1, x2, y2),
                        confidence=conf,
                        class_id=cls_id,
                        class_name=cls_name
                    ))

        return detections

    def detect_batch(self, frames: List[np.ndarray]) -> List[List[Detection]]:
        results = self.model(
            frames,
            conf=self.confidence,
            device=self.device,
            imgsz=self.input_size,
            verbose=False
        )

        batch_detections = []
        for result in results:
            detections = []
            boxes = result.boxes
            if boxes is not None:
                for box in boxes:
                    x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    cls_name = self.model.names[cls_id]
                    detections.append(Detection(
                        bbox=(x1, y1, x2, y2),
                        confidence=conf,
                        class_id=cls_id,
                        class_name=cls_name
                    ))
            batch_detections.append(detections)

        return batch_detections
