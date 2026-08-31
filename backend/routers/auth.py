from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from db import get_db
from deps.auth import get_current_user
from models.db_models import User
from services.auth_service import create_access_token, hash_password, verify_password

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def _user_dict(user: User) -> dict:
    return {"id": str(user.id), "email": user.email, "full_name": user.full_name}


def _auth_response(user: User) -> dict:
    return {"access_token": create_access_token(str(user.id)), "token_type": "bearer", "user": _user_dict(user)}


@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest, db: Session = Depends(get_db)):
    if len(request.password) < 8:
        raise HTTPException(status_code=422, detail="Password must be at least 8 characters")

    existing = db.query(User).filter(User.email == request.email.lower()).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(
        email=request.email.lower(),
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return _auth_response(user)


@router.post("/auth/login")
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == request.email.lower()).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    return _auth_response(user)


@router.get("/auth/me")
def me(current_user: User = Depends(get_current_user)):
    return _user_dict(current_user)
