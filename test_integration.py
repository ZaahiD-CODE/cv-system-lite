import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import cv2
import time

def test_pipeline_integration():
    print("Testing Pipeline integration...", end=" ")
    
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter('/tmp/test_pipe.avi', fourcc, 25.0, (640, 480))
    for i in range(30):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        cv2.putText(frame, f"Frame {i}", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        out.write(frame)
    out.release()

    from src.pipeline import Pipeline

    config = {
        "pipeline": {
            "source_type": "video",
            "source_path": "/tmp/test_pipe.avi",
            "detector": {
                "model": "yolov8n.pt",
                "confidence": 0.5,
                "device": "cpu",
                "input_size": 640
            },
            "tracker": {
                "type": "centroid",
                "max_age": 30,
                "min_hits": 2,
                "iou_threshold": 0.3
            },
            "counter": {
                "mode": "zone",
                "zones": [],
                "min_object_size": 50
            },
            "output": {
                "show": False,
                "save": False,
                "output_path": "/tmp/test_pipe_output/"
            }
        }
    }

    pipeline = Pipeline(config=config)

    zone_points = np.array([[0, 0], [300, 0], [300, 300], [0, 300]])
    pipeline.add_zone("Zone A", zone_points)

    assert pipeline.source.open() == True
    assert pipeline.detector.model is not None

    frame_count = 0
    while True:
        ret, frame = pipeline.source.read()
        if not ret:
            break

        detections = pipeline.detector.detect(frame)
        tracks = pipeline.tracker.update(detections)
        counts = pipeline.counter.update(tracks, frame.shape[:2])
        frame_count += 1

    assert frame_count == 30
    assert "Zone A" in pipeline.counter.get_counts()

    pipeline.analytics.log_frame([], [], pipeline.counter.get_counts(), 25.0)
    summary = pipeline.analytics.get_summary()
    assert summary["total_frames"] == 1

    json_path = pipeline.analytics.export_json()
    csv_path = pipeline.data_exporter.export_csv()
    assert os.path.exists(json_path)
    assert os.path.exists(csv_path)

    pipeline.source.release()

    print("OK")
    print(f"  - Processed {frame_count} frames")
    print(f"  - Zone counts: {pipeline.counter.get_counts()}")
    print(f"  - Analytics: {json_path}")
    print(f"  - Events: {csv_path}")
    return True

def test_rtsp_import():
    print("Testing RTSP Source import...", end=" ")
    from src.sources.rtsp_source import RTSPSource
    from src.sources.camera_source import CameraSource
    print("OK")
    return True

def test_config_system():
    print("Testing config system...", end=" ")
    from src.utils.config import load_config, validate_config, get_default_config
    
    config = get_default_config()
    assert validate_config(config) == True
    
    yaml_config = load_config("configs/default.yaml")
    assert validate_config(yaml_config) == True
    print("OK")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("CV System - Integration Tests")
    print("=" * 50)
    
    results = []
    for test in [test_config_system, test_rtsp_import, test_pipeline_integration]:
        try:
            ok = test()
            results.append(ok)
        except Exception as e:
            print(f"FAILED: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} passed")
    
    if passed == total:
        print("All integration tests passed!")
    else:
        sys.exit(1)
