import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(config_path: str) -> Dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    
    return config


def validate_config(config: Dict[str, Any]) -> bool:
    required_sections = ["pipeline"]
    for section in required_sections:
        if section not in config:
            raise ValueError(f"Missing required section: {section}")
    
    pipeline = config["pipeline"]
    
    if "source_type" not in pipeline:
        raise ValueError("Missing 'source_type' in pipeline config")
    
    if "detector" not in pipeline:
        raise ValueError("Missing 'detector' in pipeline config")
    
    detector = pipeline["detector"]
    if "model" not in detector:
        raise ValueError("Missing 'model' in detector config")
    
    return True


def get_default_config() -> Dict[str, Any]:
    return {
        "pipeline": {
            "source_type": "video",
            "source_path": "0",
            "detector": {
                "model": "yolo12n.pt",
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
                "save": False,
                "output_path": "output/"
            }
        }
    }
