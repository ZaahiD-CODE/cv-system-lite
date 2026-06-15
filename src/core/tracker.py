import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Track:
    track_id: int
    bbox: Tuple[int, int, int, int]
    class_id: int
    class_name: str
    confidence: float
    age: int = 0
    hits: int = 1
    time_since_update: int = 0
    history: List[Tuple[int, int]] = field(default_factory=list)
    centroid: Tuple[int, int] = (0, 0)

    def __post_init__(self):
        x1, y1, x2, y2 = self.bbox
        self.centroid = ((x1 + x2) // 2, (y1 + y2) // 2)

    def update(self, bbox: Tuple[int, int, int, int], confidence: float):
        self.history.append(self.centroid)
        self.bbox = bbox
        self.confidence = confidence
        x1, y1, x2, y2 = bbox
        self.centroid = ((x1 + x2) // 2, (y1 + y2) // 2)
        self.hits += 1
        self.time_since_update = 0
        self.age += 1


class Tracker:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tracks: Dict[int, Track] = {}
        self.next_id = 1
        self.frame_count = 0
        self.track_type = config.get("type", "centroid")
        self.max_age = config.get("max_age", 30)
        self.min_hits = config.get("min_hits", 3)
        self.iou_threshold = config.get("iou_threshold", 0.3)
        self.distance_threshold = config.get("distance_threshold", 100)
        self._kalman_filters: Dict[int, Any] = {}

    def update(self, detections: List[Any]) -> List[Track]:
        self.frame_count += 1
        
        if self.track_type == "centroid":
            return self._update_centroid(detections)
        elif self.track_type == "iou":
            return self._update_iou(detections)
        else:
            return self._update_centroid(detections)

    def _update_centroid(self, detections) -> List[Track]:
        det_centroids = []
        det_bboxes = []
        det_classes = []
        
        for det in detections:
            x1, y1, x2, y2 = det.bbox
            centroid = ((x1 + x2) // 2, (y1 + y2) // 2)
            det_centroids.append(centroid)
            det_bboxes.append(det.bbox)
            det_classes.append(det.class_id)

        matched = []
        unmatched_dets = list(range(len(detections)))
        unmatched_tracks = list(self.tracks.keys())

        if self.tracks and det_centroids:
            track_ids = list(self.tracks.keys())
            track_centroids = [self.tracks[tid].centroid for tid in track_ids]
            
            cost_matrix = np.zeros((len(det_centroids), len(track_centroids)))
            for i, det_c in enumerate(det_centroids):
                for j, track_c in enumerate(track_centroids):
                    cost_matrix[i, j] = np.sqrt(
                        (det_c[0] - track_c[0]) ** 2 + 
                        (det_c[1] - track_c[1]) ** 2
                    )

            for _ in range(min(len(det_centroids), len(track_centroids))):
                if cost_matrix.size == 0:
                    break
                min_idx = np.unravel_index(cost_matrix.argmin(), cost_matrix.shape)
                if cost_matrix[min_idx] < self.distance_threshold:
                    det_idx, track_idx = min_idx
                    matched.append((det_idx, track_ids[track_idx]))
                    unmatched_dets.remove(det_idx)
                    unmatched_tracks.remove(track_ids[track_idx])
                    cost_matrix[det_idx, :] = float('inf')
                    cost_matrix[:, track_idx] = float('inf')

        for det_idx, track_id in matched:
            det = detections[det_idx]
            self.tracks[track_id].update(det.bbox, det.confidence)

        for det_idx in unmatched_dets:
            det = detections[det_idx]
            track = Track(
                track_id=self.next_id,
                bbox=det.bbox,
                class_id=det.class_id,
                class_name=det.class_name,
                confidence=det.confidence
            )
            self.tracks[self.next_id] = track
            self.next_id += 1

        to_delete = []
        for track_id in self.tracks:
            self.tracks[track_id].time_since_update += 1
            self.tracks[track_id].age += 1
            if self.tracks[track_id].time_since_update > self.max_age:
                to_delete.append(track_id)

        for track_id in to_delete:
            del self.tracks[track_id]

        return [t for t in self.tracks.values() if t.hits >= self.min_hits]

    def _update_iou(self, detections) -> List[Track]:
        import warnings
        warnings.warn("IoU tracker not implemented, falling back to centroid", RuntimeWarning)
        return self._update_centroid(detections)

    def get_tracks_by_class(self, class_id: int) -> List[Track]:
        return [t for t in self.tracks.values() if t.class_id == class_id]

    def get_active_tracks(self) -> List[Track]:
        return [t for t in self.tracks.values() if t.hits >= self.min_hits]

    def reset(self):
        self.tracks.clear()
        self.next_id = 1
        self.frame_count = 0
