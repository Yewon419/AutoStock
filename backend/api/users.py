from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import get_current_user
from services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    username: str
    email: EmailStr
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str


@router.post("/register", status_code=201)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    user = user_service.register(db, req.username, req.email, req.password)
    return {"id": user.id, "username": user.username, "email": user.email}


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    return user_service.login(db, req.username, req.password)


@router.get("/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user
