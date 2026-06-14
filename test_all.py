import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import cv2
import time

def test_detector():
    print("[1/5] Testing Detector...", end=" ")
    from src.core.detector import Detector, Detection
    
    config = {"model": "yolo12n.pt", "confidence": 0.5, "device": "cpu", "input_size": 640}
    detector = Detector(config)
    
    frame = np.random.randint(0, 255, (640, 640, 3), dtype=np.uint8)
    detections = detector.detect(frame)
    
    assert isinstance(detections, list)
    print(f"OK (detected {len(detections)} objects on random frame)")
    return True

def test_tracker():
    print("[2/5] Testing Tracker...", end=" ")
    from src.core.tracker import Tracker, Track
    from src.core.detector import Detection
    
    config = {"type": "centroid", "max_age": 30, "min_hits": 3, "iou_threshold": 0.3}
    tracker = Tracker(config)
    
    det1 = Detection(bbox=(100, 100, 200, 200), confidence=0.9, class_id=0, class_name="person")
    det2 = Detection(bbox=(300, 300, 400, 400), confidence=0.8, class_id=1, class_name="car")
    
    frame1 = [det1, det2]
    tracks1 = tracker.update(frame1)
    assert len(tracks1) >= 0
    
    det1_moved = Detection(bbox=(110, 110, 210, 210), confidence=0.9, class_id=0, class_name="person")
    det2_moved = Detection(bbox=(310, 310, 410, 410), confidence=0.8, class_id=1, class_name="car")
    frame2 = [det1_moved, det2_moved]
    
    for _ in range(4):
        tracks = tracker.update(frame2)
    
    assert len(tracker.tracks) >= 1
    print(f"OK (tracked {len(tracker.tracks)} objects)")
    return True

def test_counter():
    print("[3/5] Testing Counter...", end=" ")
    from src.core.counter import Counter, Zone
    from src.core.tracker import Track
    
    config = {"mode": "zone", "min_object_size": 50}
    counter = Counter(config)
    
    zone_points = np.array([[0, 0], [300, 0], [300, 300], [0, 300]])
    counter.add_zone("TestZone", zone_points)
    
    track_in = Track(track_id=1, bbox=(50, 50, 100, 100), class_id=0, class_name="person", confidence=0.9)
    track_out = Track(track_id=2, bbox=(400, 400, 500, 500), class_id=0, class_name="person", confidence=0.9)
    
    counts = counter.update([track_in, track_out], (640, 640))
    
    assert "TestZone" in counts
    assert counts["TestZone"] == 1
    print(f"OK (zone count={counts['TestZone']})")
    return True

def test_source():
    print("[4/5] Testing Video Source...", end=" ")
    from src.sources.video_source import VideoSource
    
    fourcc = cv2.VideoWriter_fourcc(*'XVID')
    out = cv2.VideoWriter('/tmp/test_video.avi', fourcc, 25.0, (640, 480))
    for _ in range(50):
        frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
        out.write(frame)
    out.release()
    
    source = VideoSource("/tmp/test_video.avi")
    assert source.open() == True
    assert source.get_width() == 640
    assert source.get_height() == 480
    
    count = 0
    while True:
        ret, frame = source.read()
        if not ret:
            break
        count += 1
    
    source.release()
    assert count == 50
    print(f"OK (read {count} frames)")
    return True

def test_analytics():
    print("[5/5] Testing Analytics + Visualizer...", end=" ")
    from src.analytics.analytics import Analytics
    from src.analytics.data_exporter import DataExporter
    from src.visualization.visualizer import Visualizer
    from src.core.detector import Detection
    from src.core.tracker import Track
    
    analytics = Analytics("/tmp/test_analytics")
    exporter = DataExporter("/tmp/test_analytics")
    vis = Visualizer()
    
    det = Detection(bbox=(100, 100, 200, 200), confidence=0.9, class_id=0, class_name="person")
    track = Track(track_id=1, bbox=(100, 100, 200, 200), class_id=0, class_name="person", confidence=0.9)
    counts = {"Zone1": 5}
    
    analytics.log_frame([det], [track], counts, 30.0)
    exporter.log_detection(1, [det])
    exporter.log_tracking(1, [track])
    exporter.log_counting(1, counts)
    
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    output = vis.visualize(frame, detections=[det], tracks=[track], counts=counts, fps=30.0)
    assert output.shape == frame.shape
    
    json_path = analytics.export_json()
    csv_path = exporter.export_csv()
    assert os.path.exists(json_path)
    assert os.path.exists(csv_path)
    
    print("OK")
    return True

if __name__ == "__main__":
    print("=" * 50)
    print("CV System - Component Tests")
    print("=" * 50)
    
    results = []
    tests = [test_detector, test_tracker, test_counter, test_source, test_analytics]
    
    for test in tests:
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
        print("All tests passed!")
    else:
        print("Some tests failed.")
        sys.exit(1)
