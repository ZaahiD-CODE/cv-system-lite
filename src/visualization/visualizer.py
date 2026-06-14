import cv2
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from ..core.tracker import Track
from ..core.counter import Zone, CountingLine


class Visualizer:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.show_detections = self.config.get("show_detections", True)
        self.show_tracks = self.config.get("show_tracks", True)
        self.show_counts = self.config.get("show_counts", True)
        self.show_zones = self.config.get("show_zones", True)
        self.show_fps = self.config.get("show_fps", True)
        
        self.colors = [
            (255, 0, 0), (0, 255, 0), (0, 0, 255),
            (255, 255, 0), (0, 255, 255), (255, 0, 255),
            (128, 0, 0), (0, 128, 0), (0, 0, 128),
            (128, 128, 0), (0, 128, 128), (128, 0, 128)
        ]

    def draw_detections(self, frame: np.ndarray, detections: List[Any]) -> np.ndarray:
        if not self.show_detections:
            return frame
        
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            color = self.colors[det.class_id % len(self.colors)]
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            label = f"{det.class_name}: {det.confidence:.2f}"
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(frame, (x1, y1 - h - 10), (x1 + w, y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return frame

    def draw_tracks(self, frame: np.ndarray, tracks: List[Track]) -> np.ndarray:
        if not self.show_tracks:
            return frame
        
        for track in tracks:
            color = self.colors[track.track_id % len(self.colors)]
            x1, y1, x2, y2 = track.bbox
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            label = f"ID: {track.track_id}"
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
            cv2.rectangle(frame, (x1, y1 - h - 10), (x1 + w, y1), color, -1)
            cv2.putText(frame, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            
            if len(track.history) > 1:
                for i in range(1, len(track.history)):
                    pt1 = track.history[i - 1]
                    pt2 = track.history[i]
                    cv2.line(frame, pt1, pt2, color, 2)
            
            cv2.circle(frame, track.centroid, 5, color, -1)
        
        return frame

    def draw_zones(self, frame: np.ndarray, zones: List[Zone]) -> np.ndarray:
        if not self.show_zones:
            return frame
        
        for zone in zones:
            pts = zone.points.reshape((-1, 1, 2)).astype(np.int32)
            overlay = frame.copy()
            cv2.fillPoly(overlay, [pts], (0, 255, 0, 50))
            cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
            
            label = f"{zone.name}: {zone.count}"
            x, y = zone.points.mean(axis=0).astype(int)
            cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        return frame

    def draw_lines(self, frame: np.ndarray, lines: List[CountingLine]) -> np.ndarray:
        for line in lines:
            cv2.line(frame, line.start, line.end, (0, 0, 255), 2)
            
            mid_x = (line.start[0] + line.end[0]) // 2
            mid_y = (line.start[1] + line.end[1]) // 2
            
            label_up = f"UP: {line.count_up}"
            label_down = f"DOWN: {line.count_down}"
            cv2.putText(frame, label_up, (mid_x - 50, mid_y - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
            cv2.putText(frame, label_down, (mid_x - 50, mid_y + 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return frame

    def draw_counts(self, frame: np.ndarray, counts: Dict[str, int]) -> np.ndarray:
        if not self.show_counts:
            return frame
        
        y_offset = 30
        for name, count in counts.items():
            label = f"{name}: {count}"
            cv2.putText(frame, label, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
            y_offset += 30
        
        return frame

    def draw_fps(self, frame: np.ndarray, fps: float) -> np.ndarray:
        if not self.show_fps:
            return frame
        
        label = f"FPS: {fps:.1f}"
        cv2.putText(frame, label, (frame.shape[1] - 150, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        return frame

    def draw_info(self, frame: np.ndarray, info: Dict[str, Any]) -> np.ndarray:
        y_offset = frame.shape[0] - 30
        for key, value in info.items():
            label = f"{key}: {value}"
            cv2.putText(frame, label, (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y_offset -= 25
        
        return frame

    def visualize(self, frame: np.ndarray, detections: List[Any] = None,
                  tracks: List[Track] = None, counts: Dict[str, int] = None,
                  zones: List[Zone] = None, lines: List[CountingLine] = None,
                  fps: float = 0.0) -> np.ndarray:
        if detections:
            frame = self.draw_detections(frame, detections)
        
        if tracks:
            frame = self.draw_tracks(frame, tracks)
        
        if zones:
            frame = self.draw_zones(frame, zones)
        
        if lines:
            frame = self.draw_lines(frame, lines)
        
        if counts:
            frame = self.draw_counts(frame, counts)
        
        if self.show_fps:
            frame = self.draw_fps(frame, fps)
        
        return frame
