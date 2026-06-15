import os
import json
import shutil
import random
import threading
import time
from pathlib import Path
from typing import Dict, List, Optional
import cv2
import numpy as np

DATASETS_DIR = Path("/root/cv_system/datasets")
MODELS_DIR = Path("/root/cv_system/models")

training_jobs: Dict[int, dict] = {}
training_lock = threading.Lock()


def get_dataset_dir(object_id: int) -> Path:
    return DATASETS_DIR / f"object_{object_id}"


def save_annotation(object_id: int, frame_jpeg: bytes, bbox: List[int], class_id: int = 0):
    ds_dir = get_dataset_dir(object_id)
    images_dir = ds_dir / "images" / "train"
    labels_dir = ds_dir / "labels" / "train"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    existing = list(images_dir.glob("*.jpg"))
    idx = len(existing)

    img_path = images_dir / f"{idx:06d}.jpg"
    with open(img_path, "wb") as f:
        f.write(frame_jpeg)

    img = cv2.imdecode(np.frombuffer(frame_jpeg, np.uint8), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    x1, y1, x2, y2 = bbox
    x_center = ((x1 + x2) / 2) / w
    y_center = ((y1 + y2) / 2) / h
    bw = (x2 - x1) / w
    bh = (y2 - y1) / h

    label_path = labels_dir / f"{idx:06d}.txt"
    with open(label_path, "w") as f:
        f.write(f"{class_id} {x_center:.6f} {y_center:.6f} {bw:.6f} {bh:.6f}\n")

    return idx


def prepare_dataset(object_id: int, train_split: float = 0.8) -> str:
    ds_dir = get_dataset_dir(object_id)
    all_images = sorted((ds_dir / "images" / "train").glob("*.jpg"))
    all_labels = sorted((ds_dir / "labels" / "train").glob("*.txt"))

    if len(all_images) < 5:
        raise ValueError(f"Need at least 5 annotated frames, have {len(all_images)}")

    val_images_dir = ds_dir / "images" / "val"
    val_labels_dir = ds_dir / "labels" / "val"
    val_images_dir.mkdir(parents=True, exist_ok=True)
    val_labels_dir.mkdir(parents=True, exist_ok=True)

    for f in val_images_dir.glob("*.jpg"):
        f.unlink()
    for f in val_labels_dir.glob("*.txt"):
        f.unlink()

    combined = list(zip(all_images, all_labels))
    random.shuffle(combined)
    split_idx = int(len(combined) * train_split)
    train_pairs = combined[:split_idx]
    val_pairs = combined[split_idx:]

    for i, (img, lbl) in enumerate(val_pairs):
        shutil.copy2(img, val_images_dir / f"{i:06d}.jpg")
        shutil.copy2(lbl, val_labels_dir / f"{i:06d}.txt")

    class_name = f"custom_{object_id}"
    data_yaml = f"""path: {ds_dir}
train: images/train
val: images/val
names:
  0: {class_name}
nc: 1
"""
    yaml_path = ds_dir / "data.yaml"
    with open(yaml_path, "w") as f:
        f.write(data_yaml)

    return str(yaml_path)


def start_training(object_id: int, name: str, epochs: int = 30, base_model: str = "yolo12n.pt"):
    with training_lock:
        if object_id in training_jobs and training_jobs[object_id]["status"] == "training":
            return False
        training_jobs[object_id] = {
            "status": "training",
            "progress": 0,
            "epoch": 0,
            "total_epochs": epochs,
            "metrics": {},
            "model_path": None,
            "error": None,
        }

    base_stem = Path(base_model).stem.replace(".pt", "")
    safe_name = name.lower().replace(" ", "_").replace("-", "_")
    model_name = f"{base_stem}_{safe_name}"

    def _train():
        try:
            data_yaml = prepare_dataset(object_id)
            with training_lock:
                training_jobs[object_id]["progress"] = 5

            from ultralytics import YOLO

            model = YOLO(base_model)
            with training_lock:
                training_jobs[object_id]["progress"] = 10

            results = model.train(
                data=data_yaml,
                epochs=epochs,
                imgsz=640,
                batch=8,
                device="cpu",
                workers=2,
                project=str(MODELS_DIR),
                name=model_name,
                exist_ok=True,
                patience=10,
                verbose=False,
            )

            best_model = MODELS_DIR / model_name / "weights" / "best.pt"
            if best_model.exists():
                final_path = MODELS_DIR / f"{model_name}.pt"
                shutil.copy2(best_model, final_path)
                with training_lock:
                    training_jobs[object_id]["model_path"] = str(final_path)
                    training_jobs[object_id]["status"] = "ready"
                    training_jobs[object_id]["progress"] = 100
            else:
                with training_lock:
                    training_jobs[object_id]["status"] = "failed"
                    training_jobs[object_id]["error"] = "Model file not found"

        except Exception as e:
            with training_lock:
                training_jobs[object_id]["status"] = "failed"
                training_jobs[object_id]["error"] = str(e)

    thread = threading.Thread(target=_train, daemon=True)
    thread.start()
    return True


def get_training_status(object_id: int) -> Optional[dict]:
    with training_lock:
        return training_jobs.get(object_id)


def get_dataset_info(object_id: int) -> dict:
    ds_dir = get_dataset_dir(object_id)
    train_images = list((ds_dir / "images" / "train").glob("*.jpg")) if (ds_dir / "images" / "train").exists() else []
    val_images = list((ds_dir / "images" / "val").glob("*.jpg")) if (ds_dir / "images" / "val").exists() else []
    return {
        "train_count": len(train_images),
        "val_count": len(val_images),
        "total": len(train_images) + len(val_images),
    }
