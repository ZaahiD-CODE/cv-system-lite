import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, DateTime, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

DATABASE_URL = "sqlite:///./cv_system.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(200), nullable=False)
    role = Column(String(20), default="operator")  # admin, operator
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    streams = relationship("UserStream", back_populates="user")


class Stream(Base):
    __tablename__ = "streams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    source_type = Column(String(20), nullable=False)  # rtsp, video, camera
    source_path = Column(String(500), nullable=False)
    is_active = Column(Boolean, default=True)
    detector_model = Column(String(100), default="yolov8n.pt")
    confidence = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    zones = relationship("Zone", back_populates="stream", cascade="all, delete-orphan")
    lines = relationship("Line", back_populates="stream", cascade="all, delete-orphan")
    counters = relationship("Counter", back_populates="stream", cascade="all, delete-orphan")
    user_streams = relationship("UserStream", back_populates="stream", cascade="all, delete-orphan")


class Zone(Base):
    __tablename__ = "zones"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("streams.id"), nullable=False)
    name = Column(String(100), nullable=False)
    points = Column(JSON, nullable=False)  # [[x1,y1], [x2,y2], ...]
    is_active = Column(Boolean, default=True)

    stream = relationship("Stream", back_populates="zones")
    counters = relationship("Counter", back_populates="zone", cascade="all, delete-orphan")


class Line(Base):
    __tablename__ = "lines"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("streams.id"), nullable=False)
    name = Column(String(100), nullable=False)
    start = Column(JSON, nullable=False)   # [x, y]
    end = Column(JSON, nullable=False)     # [x, y]
    direction = Column(String(10), default="up")  # up / down
    is_active = Column(Boolean, default=True)

    stream = relationship("Stream", back_populates="lines")
    counters = relationship("Counter", back_populates="line", cascade="all, delete-orphan")


class Counter(Base):
    __tablename__ = "counters"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("streams.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("zones.id"), nullable=True)
    line_id = Column(Integer, ForeignKey("lines.id"), nullable=True)
    name = Column(String(100), nullable=False)
    type = Column(String(20), default="zone")  # zone, line
    class_filter = Column(JSON, nullable=True)  # [0, 1, 2] - class IDs to count
    is_active = Column(Boolean, default=True)
    current_count = Column(Integer, default=0)
    total_count = Column(Integer, default=0)

    stream = relationship("Stream", back_populates="counters")
    zone = relationship("Zone", back_populates="counters")
    line = relationship("Line", back_populates="counters")


class UserStream(Base):
    __tablename__ = "user_streams"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    stream_id = Column(Integer, ForeignKey("streams.id"), nullable=False)

    user = relationship("User", back_populates="streams")
    stream = relationship("Stream", back_populates="user_streams")


class CustomObject(Base):
    __tablename__ = "custom_objects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    model_path = Column(String(500), nullable=True)
    status = Column(String(20), default="pending")  # pending, collecting, training, ready, failed
    progress = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class DetectionEvent(Base):
    __tablename__ = "detection_events"

    id = Column(Integer, primary_key=True, index=True)
    stream_id = Column(Integer, ForeignKey("streams.id"), nullable=False)
    frame_id = Column(Integer, nullable=False)
    class_name = Column(String(100), nullable=False)
    class_id = Column(Integer, nullable=False)
    confidence = Column(Float, nullable=False)
    bbox_x1 = Column(Integer, nullable=False)
    bbox_y1 = Column(Integer, nullable=False)
    bbox_x2 = Column(Integer, nullable=False)
    bbox_y2 = Column(Integer, nullable=False)
    track_id = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)


def init_db():
    Base.metadata.create_all(bind=engine)
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'cv_system.db')
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        # Add lines table if missing
        tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if 'lines' not in tables:
            cursor.execute("""CREATE TABLE lines (
                id INTEGER PRIMARY KEY, stream_id INTEGER NOT NULL, name TEXT NOT NULL,
                start JSON NOT NULL, end JSON NOT NULL, direction TEXT DEFAULT 'up',
                is_active BOOLEAN DEFAULT 1, FOREIGN KEY(stream_id) REFERENCES streams(id)
            )""")
        # Add line_id column to counters if missing
        cols = [row[1] for row in cursor.execute("PRAGMA table_info(counters)").fetchall()]
        if 'line_id' not in cols:
            cursor.execute("ALTER TABLE counters ADD COLUMN line_id INTEGER REFERENCES lines(id)")
        # Recreate custom_objects without stream_id if needed
        co_cols = [row[1] for row in cursor.execute("PRAGMA table_info(custom_objects)").fetchall()]
        if 'stream_id' in co_cols or 'bbox' in co_cols or 'sample_image' in co_cols:
            cursor.execute("DROP TABLE IF EXISTS custom_objects_backup")
            cursor.execute("ALTER TABLE custom_objects RENAME TO custom_objects_backup")
            cursor.execute("""CREATE TABLE custom_objects (
                id INTEGER PRIMARY KEY, name TEXT NOT NULL, model_path TEXT,
                status TEXT DEFAULT 'pending', progress INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            cursor.execute("INSERT INTO custom_objects (id, name, status, progress, created_at) SELECT id, name, status, progress, created_at FROM custom_objects_backup")
            cursor.execute("DROP TABLE custom_objects_backup")
        if 'model_path' not in co_cols:
            cursor.execute("ALTER TABLE custom_objects ADD COLUMN model_path TEXT")
        conn.commit()
        conn.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
