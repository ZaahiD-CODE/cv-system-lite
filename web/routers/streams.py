from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Optional

from ..database import get_db, Stream, Zone, Line, Counter, UserStream, User
from ..auth import get_current_user, require_admin

router = APIRouter(prefix="/api/streams", tags=["streams"])


class StreamCreate(BaseModel):
    name: str
    source_type: str
    source_path: str
    detector_model: str = "yolov8n.pt"
    confidence: float = 0.5

class StreamUpdate(BaseModel):
    name: Optional[str] = None
    source_type: Optional[str] = None
    source_path: Optional[str] = None
    detector_model: Optional[str] = None
    confidence: Optional[float] = None
    is_active: Optional[bool] = None

class ZoneCreate(BaseModel):
    name: str
    points: List[List[int]]

class LineCreate(BaseModel):
    name: str
    start: List[int]
    end: List[int]
    direction: str = "up"

class CounterCreate(BaseModel):
    name: str
    type: str = "zone"
    zone_id: Optional[int] = None
    line_id: Optional[int] = None
    class_filter: Optional[List[int]] = None

class CounterUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    zone_id: Optional[int] = None
    line_id: Optional[int] = None
    class_filter: Optional[List[int]] = None

class StreamResponse(BaseModel):
    id: int
    name: str
    source_type: str
    source_path: str
    is_active: bool
    detector_model: str
    confidence: float
    zones: List[dict] = []
    lines: List[dict] = []
    counters: List[dict] = []
    class Config:
        from_attributes = True


def _serialize_zone(z):
    return {"id": z.id, "name": z.name, "points": z.points, "is_active": z.is_active}

def _serialize_line(l):
    return {"id": l.id, "name": l.name, "start": l.start, "end": l.end, "direction": l.direction, "is_active": l.is_active}

def _serialize_counter(c):
    return {
        "id": c.id, "name": c.name, "type": c.type,
        "zone_id": c.zone_id, "line_id": c.line_id,
        "class_filter": c.class_filter, "is_active": c.is_active,
        "current_count": c.current_count, "total_count": c.total_count,
    }


@router.get("/", response_model=List[StreamResponse])
async def list_streams(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if current_user.role == "admin":
        streams = db.query(Stream).all()
    else:
        stream_ids = [us.stream_id for us in current_user.streams]
        streams = db.query(Stream).filter(Stream.id.in_(stream_ids)).all()
    return [
        StreamResponse(
            id=s.id, name=s.name, source_type=s.source_type, source_path=s.source_path,
            is_active=s.is_active, detector_model=s.detector_model, confidence=s.confidence,
            zones=[_serialize_zone(z) for z in s.zones],
            lines=[_serialize_line(l) for l in s.lines],
            counters=[_serialize_counter(c) for c in s.counters],
        ) for s in streams
    ]


@router.get("/{stream_id}", response_model=StreamResponse)
async def get_stream(stream_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    if current_user.role != "admin":
        has_access = db.query(UserStream).filter(UserStream.user_id == current_user.id, UserStream.stream_id == stream_id).first()
        if not has_access:
            raise HTTPException(status_code=403, detail="No access")
    return StreamResponse(
        id=stream.id, name=stream.name, source_type=stream.source_type, source_path=stream.source_path,
        is_active=stream.is_active, detector_model=stream.detector_model, confidence=stream.confidence,
        zones=[_serialize_zone(z) for z in stream.zones],
        lines=[_serialize_line(l) for l in stream.lines],
        counters=[_serialize_counter(c) for c in stream.counters],
    )


@router.post("/", response_model=StreamResponse)
async def create_stream(request: StreamCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    stream = Stream(**request.dict())
    db.add(stream)
    db.commit()
    db.refresh(stream)
    return StreamResponse(
        id=stream.id, name=stream.name, source_type=stream.source_type, source_path=stream.source_path,
        is_active=stream.is_active, detector_model=stream.detector_model, confidence=stream.confidence,
    )


@router.put("/{stream_id}", response_model=StreamResponse)
async def update_stream(stream_id: int, request: StreamUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    for field, value in request.dict(exclude_unset=True).items():
        setattr(stream, field, value)
    db.commit()
    db.refresh(stream)
    return StreamResponse(
        id=stream.id, name=stream.name, source_type=stream.source_type, source_path=stream.source_path,
        is_active=stream.is_active, detector_model=stream.detector_model, confidence=stream.confidence,
        zones=[_serialize_zone(z) for z in stream.zones],
        lines=[_serialize_line(l) for l in stream.lines],
        counters=[_serialize_counter(c) for c in stream.counters],
    )


@router.delete("/{stream_id}")
async def delete_stream(stream_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    db.delete(stream)
    db.commit()
    return {"message": "Stream deleted"}


# --- ZONES ---

@router.post("/{stream_id}/zones", response_model=dict)
async def add_zone(stream_id: int, request: ZoneCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    zone = Zone(stream_id=stream_id, name=request.name, points=request.points)
    db.add(zone)
    db.commit()
    db.refresh(zone)
    return _serialize_zone(zone)


@router.delete("/{stream_id}/zones/{zone_id}")
async def delete_zone(stream_id: int, zone_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    zone = db.query(Zone).filter(Zone.id == zone_id, Zone.stream_id == stream_id).first()
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    db.delete(zone)
    db.commit()
    return {"message": "Zone deleted"}


# --- LINES ---

@router.post("/{stream_id}/lines", response_model=dict)
async def add_line(stream_id: int, request: LineCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    line = Line(stream_id=stream_id, name=request.name, start=request.start, end=request.end, direction=request.direction)
    db.add(line)
    db.commit()
    db.refresh(line)
    return _serialize_line(line)


@router.delete("/{stream_id}/lines/{line_id}")
async def delete_line(stream_id: int, line_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    line = db.query(Line).filter(Line.id == line_id, Line.stream_id == stream_id).first()
    if not line:
        raise HTTPException(status_code=404, detail="Line not found")
    db.delete(line)
    db.commit()
    return {"message": "Line deleted"}


# --- COUNTERS ---

@router.post("/{stream_id}/counters", response_model=dict)
async def add_counter(stream_id: int, request: CounterCreate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    stream = db.query(Stream).filter(Stream.id == stream_id).first()
    if not stream:
        raise HTTPException(status_code=404, detail="Stream not found")
    counter = Counter(
        stream_id=stream_id, name=request.name, type=request.type,
        zone_id=request.zone_id, line_id=request.line_id, class_filter=request.class_filter,
    )
    db.add(counter)
    db.commit()
    db.refresh(counter)
    return _serialize_counter(counter)


@router.put("/{stream_id}/counters/{counter_id}", response_model=dict)
async def update_counter(stream_id: int, counter_id: int, request: CounterUpdate, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    counter = db.query(Counter).filter(Counter.id == counter_id, Counter.stream_id == stream_id).first()
    if not counter:
        raise HTTPException(status_code=404, detail="Counter not found")
    for field, value in request.dict(exclude_unset=True).items():
        setattr(counter, field, value)
    db.commit()
    db.refresh(counter)
    return _serialize_counter(counter)


@router.delete("/{stream_id}/counters/{counter_id}")
async def delete_counter(stream_id: int, counter_id: int, current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    counter = db.query(Counter).filter(Counter.id == counter_id, Counter.stream_id == stream_id).first()
    if not counter:
        raise HTTPException(status_code=404, detail="Counter not found")
    db.delete(counter)
    db.commit()
    return {"message": "Counter deleted"}
