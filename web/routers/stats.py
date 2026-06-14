from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta

from ..database import get_db, Counter, Stream, DetectionEvent
from ..auth import get_current_user

router = APIRouter(prefix="/api/stats", tags=["stats"])


class CounterStats(BaseModel):
    counter_id: int
    counter_name: str
    stream_id: int
    stream_name: str
    type: str
    current_count: int
    total_count: int
    class_filter: Optional[List[int]] = None


class StreamStats(BaseModel):
    stream_id: int
    stream_name: str
    is_active: bool
    counters: List[CounterStats]
    detection_stats: Dict[str, int]


class DetectionStat(BaseModel):
    class_name: str
    count: int
    avg_confidence: float


@router.get("/counters", response_model=List[CounterStats])
async def get_counter_stats(
    stream_id: Optional[int] = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(Counter)
    if stream_id:
        query = query.filter(Counter.stream_id == stream_id)

    counters = query.all()
    result = []
    for c in counters:
        stream = db.query(Stream).filter(Stream.id == c.stream_id).first()
        result.append(CounterStats(
            counter_id=c.id,
            counter_name=c.name,
            stream_id=c.stream_id,
            stream_name=stream.name if stream else "Unknown",
            type=c.type,
            current_count=c.current_count,
            total_count=c.total_count,
            class_filter=c.class_filter
        ))
    return result


@router.get("/streams", response_model=List[StreamStats])
async def get_stream_stats(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    streams = db.query(Stream).all()
    result = []

    for s in streams:
        counters = db.query(Counter).filter(Counter.stream_id == s.id).all()
        counter_stats = [
            CounterStats(
                counter_id=c.id, counter_name=c.name,
                stream_id=s.id, stream_name=s.name,
                type=c.type, current_count=c.current_count,
                total_count=c.total_count, class_filter=c.class_filter
            )
            for c in counters
        ]

        # Get detection stats for this stream
        detection_stats = {}
        recent_detections = db.query(
            DetectionEvent.class_name,
            func.count(DetectionEvent.id).label('count')
        ).filter(
            DetectionEvent.stream_id == s.id,
            DetectionEvent.timestamp >= datetime.utcnow() - timedelta(hours=1)
        ).group_by(DetectionEvent.class_name).all()

        for class_name, count in recent_detections:
            detection_stats[class_name] = count

        result.append(StreamStats(
            stream_id=s.id,
            stream_name=s.name,
            is_active=s.is_active,
            counters=counter_stats,
            detection_stats=detection_stats
        ))

    return result


@router.get("/detections/{stream_id}")
async def get_stream_detections(
    stream_id: int,
    limit: int = 100,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    detections = db.query(DetectionEvent).filter(
        DetectionEvent.stream_id == stream_id
    ).order_by(DetectionEvent.timestamp.desc()).limit(limit).all()

    return [
        {
            "id": d.id,
            "frame_id": d.frame_id,
            "class_name": d.class_name,
            "confidence": d.confidence,
            "bbox": [d.bbox_x1, d.bbox_y1, d.bbox_x2, d.bbox_y2],
            "track_id": d.track_id,
            "timestamp": d.timestamp.isoformat()
        }
        for d in detections
    ]


@router.get("/dashboard")
async def get_dashboard_stats(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    total_streams = db.query(Stream).count()
    active_streams = db.query(Stream).filter(Stream.is_active == True).count()
    total_counters = db.query(Counter).count()

    # Get today's detections
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    today_detections = db.query(func.count(DetectionEvent.id)).filter(
        DetectionEvent.timestamp >= today
    ).scalar() or 0

    # Get top detected classes
    top_classes = db.query(
        DetectionEvent.class_name,
        func.count(DetectionEvent.id).label('count')
    ).filter(
        DetectionEvent.timestamp >= today
    ).group_by(DetectionEvent.class_name).order_by(
        func.count(DetectionEvent.id).desc()
    ).limit(10).all()

    return {
        "total_streams": total_streams,
        "active_streams": active_streams,
        "total_counters": total_counters,
        "today_detections": today_detections,
        "top_classes": [{"class_name": c, "count": n} for c, n in top_classes]
    }


@router.get("/system")
async def get_system_info(current_user=Depends(get_current_user)):
    import sys
    sys.path.insert(0, "/root/cv_system")
    from src.core.detector import get_gpu_info, AVAILABLE_MODELS

    return {
        "gpu": get_gpu_info(),
        "models": AVAILABLE_MODELS,
    }
