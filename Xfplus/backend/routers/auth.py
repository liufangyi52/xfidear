from fastapi import APIRouter, Depends

from backend.models import AuthResponse, LoginRequest, RegisterRequest, UserPublic
from backend.services.auth_service import current_user, login_user, register_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse)
def register(payload: RegisterRequest):
    token, user = register_user(payload)
    return AuthResponse(token=token, user=user)


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest):
    token, user = login_user(payload.username, payload.password)
    return AuthResponse(token=token, user=user)


@router.get("/me", response_model=UserPublic)
def me(user: UserPublic = Depends(current_user)):
    return user
