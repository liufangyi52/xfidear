from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.database import Base


class UserDB(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    role: Mapped[str] = mapped_column(String(40), index=True)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    community: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    salt: Mapped[str] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(128))


class AlertDB(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    disaster_type: Mapped[str] = mapped_column(String(80), default="暴雨/山洪/滑坡")
    level: Mapped[str] = mapped_column(String(40), default="橙色")
    affected_areas: Mapped[str] = mapped_column(Text, default="[]")
    started_at: Mapped[str] = mapped_column(String(80), default="")
    duration: Mapped[str] = mapped_column(String(80), default="")
    advice: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="active")
    data_source_note: Mapped[str] = mapped_column(Text, default="")
    audience_messages: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    community: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    is_pushed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    pushed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class ShelterDB(Base):
    __tablename__ = "shelters"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    area: Mapped[str] = mapped_column(String(120), index=True)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    capacity: Mapped[int] = mapped_column(Integer)
    contact: Mapped[str] = mapped_column(String(160))
    source: Mapped[str] = mapped_column(Text)


class BroadcastRecordDB(Base):
    __tablename__ = "broadcast_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[int] = mapped_column(Integer, index=True, default=0)
    alert_title: Mapped[str] = mapped_column(String(200), default="")
    audience: Mapped[str] = mapped_column(String(120), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    type: Mapped[str] = mapped_column(String(80), default="管理端推送")
    source_type: Mapped[str] = mapped_column(String(80), default="alert_push")
    play_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class MessageDB(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    target_roles: Mapped[str] = mapped_column(Text, default="[]")
    target_district: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    target_community: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    target_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    sender_id: Mapped[int] = mapped_column(Integer, index=True)
    sender_role: Mapped[str] = mapped_column(String(40), index=True)
    priority: Mapped[str] = mapped_column(String(40), index=True)
    source_type: Mapped[str] = mapped_column(String(80), default="manual")
    related_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="sent", index=True)
    reply_content: Mapped[str] = mapped_column(Text, default="")
    review_note: Mapped[str] = mapped_column(Text, default="")
    reviewed_by: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    reviewed_at: Mapped[str | None] = mapped_column(String(40), nullable=True)
    attachments: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[str] = mapped_column(String(40), index=True)


class IncidentDB(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    type: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str] = mapped_column(Text)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    district: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    community: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    scenic_area: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True, default="pending")
    reporter_role: Mapped[str] = mapped_column(String(40), index=True)
    reporter_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    nearest_shelter: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str] = mapped_column(String(240), default="")
    source_org: Mapped[str] = mapped_column(String(120), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    source_date: Mapped[str] = mapped_column(String(40), default="")
    workflow_steps: Mapped[str] = mapped_column(Text, default="[]")
    need_review: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[str] = mapped_column(String(40), index=True)
    resolved_at: Mapped[str | None] = mapped_column(String(40), nullable=True)


class NotificationLogDB(Base):
    __tablename__ = "notification_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    channel: Mapped[str] = mapped_column(String(40), default="sms_reserved")
    target: Mapped[str] = mapped_column(String(160), default="")
    title: Mapped[str] = mapped_column(String(200), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="reserved")
    created_at: Mapped[str] = mapped_column(String(40), index=True)
