import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from src.pipeline import Pipeline


def main():
    config = {
        "pipeline": {
            "source_type": "video",
            "source_path": "test_input.avi",
            "detector": {
                "model": "yolov8n.pt",
                "confidence": 0.5,
                "device": "cpu",
                "input_size": 640
            },
            "tracker": {
                "type": "centroid",
                "max_age": 30,
                "min_hits": 3,
                "iou_threshold": 0.3
            },
            "counter": {
                "mode": "zone",
                "zones": [],
                "min_object_size": 50
            },
            "output": {
                "show": True,
                "save": True,
                "output_path": "output/"
            }
        }
    }

    pipeline = Pipeline(config=config)

    pipeline.add_zone(
        name="Main Zone",
        points=np.array([[50, 50], [400, 50], [400, 400], [50, 400]])
    )

    print("Starting CV System Pipeline...")
    print("Press 'q' to quit, 'r' to reset counter")

    pipeline.start()


if __name__ == "__main__":
    main()
