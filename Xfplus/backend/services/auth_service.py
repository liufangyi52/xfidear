import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Header, HTTPException
from sqlalchemy import select

from backend.database import session_scope
from backend.db_models import UserDB
from backend.models import RegisterRequest, UserPublic

SESSIONS_FILE = Path(__file__).resolve().parents[1] / "data" / "sessions.json"
SESSIONS: dict[str, int] = {}


def _load_sessions() -> dict[str, int]:
    if not SESSIONS_FILE.exists():
        return {}
    try:
        data = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
        return {str(token): int(user_id) for token, user_id in data.items()}
    except (OSError, ValueError, TypeError):
        return {}


def _save_sessions() -> None:
    SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSIONS_FILE.write_text(json.dumps(SESSIONS, ensure_ascii=False), encoding="utf-8")


def _remember_session(token: str, user_id: int) -> None:
    SESSIONS[token] = user_id
    _save_sessions()


SESSIONS.update(_load_sessions())


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def _public(user: UserDB) -> UserPublic:
    return UserPublic(
        id=int(user.id),
        username=user.username,
        role=user.role,
        district=user.district,
        community=user.community,
    )


def register_user(payload: RegisterRequest) -> tuple[str, UserPublic]:
    if payload.role == "county_admin" and not payload.district:
        raise HTTPException(status_code=400, detail="County admin must select a district")
    if payload.role == "community_admin" and (not payload.district or not payload.community):
        raise HTTPException(status_code=400, detail="Community admin must select district and community")

    with session_scope() as db:
        exists = db.scalar(select(UserDB).where(UserDB.username == payload.username))
        if exists:
            raise HTTPException(status_code=409, detail="Username already exists")
        salt = secrets.token_hex(8)
        user = UserDB(
            username=payload.username,
            role=payload.role,
            district=payload.district,
            community=payload.community,
            salt=salt,
            password_hash=_hash_password(payload.password, salt),
        )
        db.add(user)
        db.flush()
        db.refresh(user)
        token = secrets.token_urlsafe(32)
        _remember_session(token, int(user.id))
        return token, _public(user)


def login_user(username: str, password: str) -> tuple[str, UserPublic]:
    with session_scope() as db:
        user = db.scalar(select(UserDB).where(UserDB.username == username))
        if user and user.password_hash == _hash_password(password, user.salt):
            token = secrets.token_urlsafe(32)
            _remember_session(token, int(user.id))
            return token, _public(user)
    raise HTTPException(status_code=401, detail="Invalid username or password")


def get_user_by_id(user_id: int) -> Optional[UserPublic]:
    with session_scope() as db:
        user = db.get(UserDB, user_id)
        return _public(user) if user else None


def get_user_for_token(token: str) -> Optional[UserPublic]:
    user_id = SESSIONS.get(token.strip())
    return get_user_by_id(user_id) if user_id else None


def current_user(authorization: str = Header("")) -> UserPublic:
    token = authorization.replace("Bearer ", "").strip()
    user = get_user_for_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user
