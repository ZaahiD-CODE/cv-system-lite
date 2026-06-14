from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import List, Optional

from ..database import get_db, User, UserStream, Stream
from ..auth import require_admin, get_password_hash

router = APIRouter(prefix="/api/users", tags=["users"])


class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: str = "operator"
    stream_ids: List[int] = []


class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    stream_ids: Optional[List[int]] = None


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    role: str
    is_active: bool
    stream_ids: List[int] = []

    class Config:
        from_attributes = True


class StreamAssignment(BaseModel):
    stream_ids: List[int]


@router.get("/", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    users = db.query(User).all()
    result = []
    for u in users:
        stream_ids = [us.stream_id for us in u.streams]
        result.append(UserResponse(
            id=u.id, username=u.username, email=u.email,
            role=u.role, is_active=u.is_active, stream_ids=stream_ids
        ))
    return result


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stream_ids = [us.stream_id for us in user.streams]
    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        role=user.role, is_active=user.is_active, stream_ids=stream_ids
    )


@router.post("/", response_model=UserResponse)
async def create_user(
    request: UserCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    existing = db.query(User).filter(
        (User.username == request.username) | (User.email == request.email)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username or email already exists")

    user = User(
        username=request.username,
        email=request.email,
        hashed_password=get_password_hash(request.password),
        role=request.role
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    for stream_id in request.stream_ids:
        us = UserStream(user_id=user.id, stream_id=stream_id)
        db.add(us)
    db.commit()

    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        role=user.role, is_active=user.is_active, stream_ids=request.stream_ids
    )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    request: UserUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if request.username is not None:
        user.username = request.username
    if request.email is not None:
        user.email = request.email
    if request.password is not None:
        user.hashed_password = get_password_hash(request.password)
    if request.role is not None:
        user.role = request.role
    if request.is_active is not None:
        user.is_active = request.is_active

    db.commit()

    if request.stream_ids is not None:
        db.query(UserStream).filter(UserStream.user_id == user_id).delete()
        for stream_id in request.stream_ids:
            us = UserStream(user_id=user_id, stream_id=stream_id)
            db.add(us)
        db.commit()

    db.refresh(user)
    stream_ids = [us.stream_id for us in user.streams]
    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        role=user.role, is_active=user.is_active, stream_ids=stream_ids
    )


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    db.delete(user)
    db.commit()
    return {"message": "User deleted"}


@router.post("/{user_id}/streams", response_model=UserResponse)
async def assign_streams(
    user_id: int,
    request: StreamAssignment,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.query(UserStream).filter(UserStream.user_id == user_id).delete()
    for stream_id in request.stream_ids:
        us = UserStream(user_id=user_id, stream_id=stream_id)
        db.add(us)
    db.commit()
    db.refresh(user)

    stream_ids = [us.stream_id for us in user.streams]
    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        role=user.role, is_active=user.is_active, stream_ids=stream_ids
    )
