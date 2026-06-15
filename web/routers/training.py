import base64
import cv2
import numpy as np
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from ..database import get_db, CustomObject, Stream, User
from ..auth import get_current_user, require_admin

import sys
sys.path.insert(0, "/root/cv_system")
from src.training_engine import (
    save_annotation, start_training, get_training_status,
    get_dataset_info, get_dataset_dir
)

router = APIRouter(prefix="/api/training", tags=["training"])


class CustomObjectCreate(BaseModel):
    name: str

class AnnotationCreate(BaseModel):
    bbox: List[int]
    frame_base64: str

class TrainRequest(BaseModel):
    epochs: int = 30
    base_model: str = "yolo12n.pt"


@router.get("/objects")
async def list_custom_objects(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    objects = db.query(CustomObject).all()
    result = []
    for o in objects:
        info = get_dataset_info(o.id)
        job = get_training_status(o.id)
        result.append({
            "id": o.id, "name": o.name,
            "status": job["status"] if job else o.status,
            "progress": job["progress"] if job else o.progress,
            "sample_count": info["total"],
            "model_path": (job.get("model_path") if job else o.model_path),
            "created_at": o.created_at.isoformat(),
        })
    return result


@router.post("/objects")
async def create_custom_object(request: CustomObjectCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    obj = CustomObject(name=request.name, status="pending")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return {"id": obj.id, "name": obj.name, "status": obj.status}


@router.delete("/objects/{object_id}")
async def delete_custom_object(object_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    obj = db.query(CustomObject).filter(CustomObject.id == object_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    import shutil
    ds_dir = get_dataset_dir(object_id)
    if ds_dir.exists():
        shutil.rmtree(ds_dir)
    db.delete(obj)
    db.commit()
    return {"message": "Deleted"}


@router.post("/objects/{object_id}/annotate")
async def add_annotation(object_id: int, request: AnnotationCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    obj = db.query(CustomObject).filter(CustomObject.id == object_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    if obj.status == "training":
        raise HTTPException(status_code=400, detail="Cannot annotate during training")
    frame_bytes = base64.b64decode(request.frame_base64)
    idx = save_annotation(object_id, frame_bytes, request.bbox, class_id=0)
    obj.status = "collecting"
    db.commit()
    info = get_dataset_info(object_id)
    return {"index": idx, "total_samples": info["total"]}


@router.get("/objects/{object_id}/samples")
async def get_samples(object_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.query(CustomObject).filter(CustomObject.id == object_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    ds_dir = get_dataset_dir(object_id)
    images_dir = ds_dir / "images" / "train"
    labels_dir = ds_dir / "labels" / "train"
    if not images_dir.exists():
        return {"samples": [], "total": 0}
    samples = []
    for img_path in sorted(images_dir.glob("*.jpg")):
        label_path = labels_dir / f"{img_path.stem}.txt"
        bbox = []
        if label_path.exists():
            with open(label_path) as f:
                parts = f.read().strip().split()
                if len(parts) == 5:
                    _, xc, yc, w, h = map(float, parts)
                    img = cv2.imread(str(img_path))
                    ih, iw = img.shape[:2]
                    bbox = [int((xc-w/2)*iw), int((yc-h/2)*ih), int((xc+w/2)*iw), int((yc+h/2)*ih)]
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()
        samples.append({"image": img_b64, "bbox": bbox, "filename": img_path.name})
    return {"samples": samples, "total": len(samples)}


@router.delete("/objects/{object_id}/samples/{filename}")
async def delete_sample(object_id: int, filename: str, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    from pathlib import Path
    ds_dir = get_dataset_dir(object_id)
    img = ds_dir / "images" / "train" / filename
    lbl = ds_dir / "labels" / "train" / f"{Path(filename).stem}.txt"
    if img.exists(): img.unlink()
    if lbl.exists(): lbl.unlink()
    return {"message": "Deleted"}


@router.post("/objects/{object_id}/train")
async def start_training_endpoint(object_id: int, request: TrainRequest, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    obj = db.query(CustomObject).filter(CustomObject.id == object_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    info = get_dataset_info(object_id)
    if info["total"] < 5:
        raise HTTPException(status_code=400, detail=f"Нужно минимум 5 кадров, есть {info['total']}")
    ok = start_training(object_id, obj.name, epochs=request.epochs, base_model=request.base_model)
    if not ok:
        raise HTTPException(status_code=400, detail="Уже обучается")
    obj.status = "training"
    db.commit()
    return {"message": "Training started"}


@router.get("/objects/{object_id}/status")
async def get_status(object_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    obj = db.query(CustomObject).filter(CustomObject.id == object_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="Not found")
    job = get_training_status(object_id)
    info = get_dataset_info(object_id)
    if job:
        if job["status"] == "ready":
            obj.status = "ready"
            obj.progress = 100
            obj.model_path = job.get("model_path")
            db.commit()
        elif job["status"] == "failed":
            obj.status = "failed"
            db.commit()
        return {"status": job["status"], "progress": job["progress"], "error": job.get("error"),
                "model_path": job.get("model_path") or obj.model_path, "samples": info["total"]}
    return {"status": obj.status, "progress": obj.progress, "error": None,
            "model_path": obj.model_path, "samples": info["total"]}


@router.get("/snapshot/{stream_id}")
async def get_stream_snapshot(stream_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    try:
        if stream.source_type == "video":
            cap = cv2.VideoCapture(stream.source_path)
        elif stream.source_type == "rtsp":
            cap = cv2.VideoCapture(stream.source_path, cv2.CAP_FFMPEG)
        else:
            cap = cv2.VideoCapture(int(stream.source_path))
        if not cap.isOpened():
            raise HTTPException(status_code=500, detail="Cannot open stream")
        ret, frame = cap.read()
        cap.release()
        if not ret:
            raise HTTPException(status_code=500, detail="Cannot read frame")
        _, buffer = cv2.imencode('.jpg', frame)
        return {"image": base64.b64encode(buffer).decode(), "width": frame.shape[1], "height": frame.shape[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


YOLO_CLASSES = {
    0: "person", 1: "bicycle", 2: "car", 3: "motorcycle", 4: "airplane", 5: "bus",
    6: "train", 7: "truck", 8: "boat", 9: "traffic light", 10: "fire hydrant",
    11: "stop sign", 12: "parking meter", 13: "bench", 14: "bird", 15: "cat",
    16: "dog", 17: "horse", 18: "sheep", 19: "cow", 20: "elephant",
    21: "bear", 22: "zebra", 23: "giraffe", 24: "backpack", 25: "umbrella",
    26: "handbag", 27: "tie", 28: "suitcase", 29: "frisbee", 30: "skis",
    31: "snowboard", 32: "sports ball", 33: "kite", 34: "baseball bat", 35: "baseball glove",
    36: "skateboard", 37: "surfboard", 38: "tennis racket", 39: "bottle", 40: "wine glass",
    41: "cup", 42: "fork", 43: "knife", 44: "spoon", 45: "bowl",
    46: "banana", 47: "apple", 48: "sandwich", 49: "orange", 50: "broccoli",
    51: "carrot", 52: "hot dog", 53: "pizza", 54: "donut", 55: "cake",
    56: "chair", 57: "couch", 58: "potted plant", 59: "bed", 60: "dining table",
    61: "toilet", 62: "tv", 63: "laptop", 64: "mouse", 65: "remote",
    66: "keyboard", 67: "cell phone", 68: "microwave", 69: "oven", 70: "toaster",
    71: "sink", 72: "refrigerator", 73: "book", 74: "clock", 75: "vase",
    76: "scissors", 77: "teddy bear", 78: "hair drier", 79: "toothbrush",
}
YOLO_CLASSES_RU = {
    0: "человек", 1: "велосипед", 2: "автомобиль", 3: "мотоцикл", 4: "самолёт", 5: "автобус",
    6: "поезд", 7: "грузовик", 8: "лодка", 9: "светофор", 10: "пожарный гидрант",
    11: "знак стоп", 12: "паркомат", 13: "скамейка", 14: "птица", 15: "кот",
    16: "собака", 17: "лошадь", 18: "овца", 19: "корова", 20: "слон",
    21: "медведь", 22: "зебра", 23: "жираф", 24: "рюкзак", 25: "зонт",
    26: "сумка", 27: "галстук", 28: "чемодан", 29: "фрисби", 30: "лыжи",
    31: "сноуборд", 32: "мяч", 33: "воздушный змей", 34: "бита", 35: "перчатка",
    36: "скейтборд", 37: "сёрфборд", 38: "ракетка", 39: "бутылка", 40: "бокал",
    41: "чашка", 42: "вилка", 43: "нож", 44: "ложка", 45: "миска",
    46: "банан", 47: "яблоко", 48: "бутерброд", 49: "апельсин", 50: "брокколи",
    51: "морковь", 52: "хот-дог", 53: "пицца", 54: "пончик", 55: "торт",
    56: "стул", 57: "диван", 58: "растение", 59: "кровать", 60: "стол",
    61: "унитаз", 62: "телевизор", 63: "ноутбук", 64: "мышь", 65: "пульт",
    66: "клавиатура", 67: "телефон", 68: "микроволновка", 69: "духовка", 70: "тостер",
    71: "раковина", 72: "холодильник", 73: "книга", 74: "часы", 75: "ваза",
    76: "ножницы", 77: "мишка", 78: "фен", 79: "зубная щётка",
}


@router.get("/classes")
async def get_all_classes(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    standard = [{"id": cid, "name": cname, "name_ru": YOLO_CLASSES_RU.get(cid, cname), "type": "standard"}
                for cid, cname in YOLO_CLASSES.items()]
    custom = db.query(CustomObject).filter(CustomObject.status == "ready").all()
    custom_list = [{"id": 1000 + c.id, "name": c.name, "name_ru": c.name, "type": "custom"} for c in custom]
    return standard + custom_list


@router.get("/models")
async def get_available_models(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    import sys
    sys.path.insert(0, "/root/cv_system")
    from src.core.detector import AVAILABLE_MODELS

    models = {k: {**v, "type": "standard"} for k, v in AVAILABLE_MODELS.items()}

    custom = db.query(CustomObject).filter(
        CustomObject.status == "ready",
        CustomObject.model_path.isnot(None)
    ).all()
    for c in custom:
        model_filename = Path(c.model_path).stem if c.model_path else f"custom_{c.id}"
        key = f"custom_{c.id}"
        models[key] = {
            "name": model_filename,
            "size": "-",
            "speed": "-",
            "accuracy": "custom",
            "type": "custom",
            "model_path": c.model_path,
        }

    return models
