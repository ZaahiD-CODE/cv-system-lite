import cv2
import time
import numpy as np
from typing import Dict, Any, Optional, List
from pathlib import Path

from .core.detector import Detector
from .core.tracker import Tracker
from .core.counter import Counter
from .sources.video_source import VideoSource
from .sources.rtsp_source import RTSPSource
from .sources.camera_source import CameraSource
from .analytics.analytics import Analytics
from .analytics.data_exporter import DataExporter
from .visualization.visualizer import Visualizer
from .utils.config import load_config, validate_config


class Pipeline:
    def __init__(self, config_path: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        if config_path:
            self.config = load_config(config_path)
        elif config:
            self.config = config
        else:
            raise ValueError("Either config_path or config must be provided")
        
        validate_config(self.config)
        
        pipeline_config = self.config["pipeline"]
        
        self.detector = Detector(pipeline_config["detector"])
        self.tracker = Tracker(pipeline_config.get("tracker", {}))
        self.counter = Counter(pipeline_config.get("counter", {}))
        self.visualizer = Visualizer(pipeline_config.get("output", {}))
        
        self.analytics = Analytics(pipeline_config.get("output", {}).get("output_path", "analytics"))
        self.data_exporter = DataExporter(pipeline_config.get("output", {}).get("output_path", "exports"))
        
        self.source = self._create_source(pipeline_config)
        self.output_config = pipeline_config.get("output", {})
        
        self.is_running = False
        self.writer: Optional[cv2.VideoWriter] = None

    def _create_source(self, pipeline_config: Dict[str, Any]):
        source_type = pipeline_config["source_type"]
        source_path = pipeline_config.get("source_path", "0")
        
        if source_type == "rtsp":
            return RTSPSource(source_path)
        elif source_type == "camera":
            camera_id = int(source_path) if source_path.isdigit() else 0
            return CameraSource(camera_id)
        elif source_type == "video":
            return VideoSource(source_path)
        else:
            raise ValueError(f"Unknown source type: {source_type}")

    def start(self):
        if not self.source.open():
            raise RuntimeError("Failed to open video source")
        
        self.is_running = True
        
        fps = self.source.get_fps()
        width = self.source.get_width()
        height = self.source.get_height()
        
        if self.output_config.get("save", False):
            output_path = self.output_config.get("output_path", "output/")
            Path(output_path).mkdir(parents=True, exist_ok=True)
            codec = cv2.VideoWriter_fourcc(*self.output_config.get("codec", "mp4v"))
            output_file = f"{output_path}output_{int(time.time())}.mp4"
            self.writer = cv2.VideoWriter(output_file, codec, fps, (width, height))
        
        print(f"Pipeline started. Source: {width}x{height} @ {fps:.1f} FPS")
        
        frame_id = 0
        prev_time = time.time()
        
        try:
            while self.is_running:
                ret, frame = self.source.read()
                if not ret:
                    from .sources.video_source import VideoSource
                    if isinstance(self.source, VideoSource):
                        break
                    continue
                
                frame_id += 1
                
                detections = self.detector.detect(frame)
                
                tracks = self.tracker.update(detections)
                
                counts = self.counter.update(tracks, frame.shape[:2])
                
                current_time = time.time()
                fps = 1.0 / (current_time - prev_time) if (current_time - prev_time) > 0 else 0
                prev_time = current_time
                
                self.analytics.log_frame(detections, tracks, counts, fps)
                
                self.data_exporter.log_detection(frame_id, detections)
                self.data_exporter.log_tracking(frame_id, tracks)
                self.data_exporter.log_counting(frame_id, counts)
                
                if self.output_config.get("show", True):
                    output_frame = self.visualizer.visualize(
                        frame.copy(),
                        detections=detections,
                        tracks=tracks,
                        counts=counts,
                        zones=self.counter.zones,
                        lines=self.counter.lines,
                        fps=fps
                    )
                    
                    cv2.imshow("CV System", output_frame)
                    
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord('q'):
                        break
                    elif key == ord('r'):
                        self.counter.reset()
                        self.tracker.reset()
                        print("Counter and tracker reset")
                
                if self.writer:
                    self.writer.write(frame)
        
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        
        if self.writer:
            self.writer.release()
        
        self.source.release()
        cv2.destroyAllWindows()
        
        summary = self.analytics.get_summary()
        print("\n=== Session Summary ===")
        print(f"Duration: {summary['session_duration_sec']} sec")
        print(f"Total Frames: {summary['total_frames']}")
        print(f"Average FPS: {summary['average_fps']}")
        print(f"Zone Counts: {summary['zone_counts']}")
        
        analytics_path = self.analytics.export_json()
        print(f"Analytics exported to: {analytics_path}")
        
        events_path = self.data_exporter.export_json()
        print(f"Events exported to: {events_path}")

    def add_zone(self, name: str, points: np.ndarray, class_filter: Optional[List[int]] = None):
        self.counter.add_zone(name, points, class_filter)

    def add_line(self, name: str, start, end, direction: str = "up", 
                 class_filter: Optional[List[int]] = None):
        self.counter.add_line(name, start, end, direction, class_filter)
