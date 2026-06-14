import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict


class CountingMode(Enum):
    ZONE = "zone"
    LINE = "line"


@dataclass
class Zone:
    name: str
    points: np.ndarray
    class_filter: Optional[List[int]] = None
    count: int = 0
    inside_tracks: Dict[int, bool] = field(default_factory=dict)


@dataclass
class CountingLine:
    name: str
    start: Tuple[int, int]
    end: Tuple[int, int]
    direction: str = "up"
    class_filter: Optional[List[int]] = None
    count_up: int = 0
    count_down: int = 0
    counted_tracks: Dict[int, str] = field(default_factory=dict)


class Counter:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.mode = CountingMode(config.get("mode", "zone"))
        self.zones: List[Zone] = []
        self.lines: List[CountingLine] = []
        self.total_counts: Dict[str, int] = defaultdict(int)
        self.min_object_size = config.get("min_object_size", 50)

    def add_zone(self, name: str, points: np.ndarray, class_filter: Optional[List[int]] = None):
        zone = Zone(name=name, points=points, class_filter=class_filter)
        self.zones.append(zone)

    def add_line(self, name: str, start: Tuple[int, int], end: Tuple[int, int], 
                 direction: str = "up", class_filter: Optional[List[int]] = None):
        line = CountingLine(
            name=name, start=start, end=end,
            direction=direction, class_filter=class_filter
        )
        self.lines.append(line)

    def update(self, tracks: List[Any], frame_shape: Tuple[int, int]) -> Dict[str, int]:
        counts = {}
        
        if self.mode == CountingMode.ZONE:
            counts = self._update_zones(tracks)
        elif self.mode == CountingMode.LINE:
            counts = self._update_lines(tracks)
        
        return counts

    def _update_zones(self, tracks: List[Any]) -> Dict[str, int]:
        counts = {}
        
        for zone in self.zones:
            current_inside = set()
            
            for track in tracks:
                if zone.class_filter and track.class_id not in zone.class_filter:
                    continue
                
                centroid = track.centroid
                if self._point_in_polygon(centroid, zone.points):
                    current_inside.add(track.track_id)
                    if track.track_id not in zone.inside_tracks:
                        zone.count += 1
                        zone.inside_tracks[track.track_id] = True
            
            to_remove = [tid for tid in zone.inside_tracks if tid not in current_inside]
            for tid in to_remove:
                del zone.inside_tracks[tid]
            
            counts[zone.name] = zone.count
            self.total_counts[zone.name] = zone.count
        
        return counts

    def _update_lines(self, tracks: List[Any]) -> Dict[str, int]:
        counts = {}
        
        for line in self.lines:
            for track in tracks:
                if line.class_filter and track.class_id not in line.class_filter:
                    continue
                
                if len(track.history) < 2:
                    continue
                
                prev_pos = track.history[-1]
                curr_pos = track.centroid
                
                if self._lines_intersect(prev_pos, curr_pos, line.start, line.end):
                    if track.track_id not in line.counted_tracks:
                        if self._get_crossing_direction(prev_pos, curr_pos, line.start, line.end) == "up":
                            line.count_up += 1
                            line.counted_tracks[track.track_id] = "up"
                        else:
                            line.count_down += 1
                            line.counted_tracks[track.track_id] = "down"
            
            counts[f"{line.name}_up"] = line.count_up
            counts[f"{line.name}_down"] = line.count_down
            self.total_counts[line.name] = line.count_up + line.count_down
        
        return counts

    def _point_in_polygon(self, point: Tuple[int, int], polygon: np.ndarray) -> bool:
        return cv2.pointPolygonTest(polygon.astype(np.float32), point, False) >= 0

    def _lines_intersect(self, p1: Tuple[int, int], p2: Tuple[int, int],
                         p3: Tuple[int, int], p4: Tuple[int, int]) -> bool:
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])
        
        A, B = p1, p2
        C, D = p3, p4
        return ccw(A, C, D) != ccw(B, C, D) and ccw(A, B, C) != ccw(A, B, D)

    def _get_crossing_direction(self, p1: Tuple[int, int], p2: Tuple[int, int],
                                line_start: Tuple[int, int], line_end: Tuple[int, int]) -> str:
        cross = (line_end[0] - line_start[0]) * (p2[1] - p1[1]) - \
                (line_end[1] - line_start[1]) * (p2[0] - p1[0])
        return "up" if cross > 0 else "down"

    def reset(self):
        for zone in self.zones:
            zone.count = 0
            zone.inside_tracks.clear()
        for line in self.lines:
            line.count_up = 0
            line.count_down = 0
            line.counted_tracks.clear()
        self.total_counts.clear()

    def get_counts(self) -> Dict[str, int]:
        return dict(self.total_counts)


import cv2
