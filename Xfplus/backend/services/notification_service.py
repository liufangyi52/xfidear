from sqlalchemy import select

from backend.database import session_scope
from backend.db_models import NotificationLogDB
from backend.models import NotificationTestRequest, now_iso


def reserve_sms_notification(payload: NotificationTestRequest) -> dict:
    with session_scope() as db:
        record = NotificationLogDB(
            channel="sms_reserved",
            target=payload.target,
            title=payload.title,
            content=payload.content,
            status="reserved",
            created_at=now_iso(),
        )
        db.add(record)
        db.flush()
        db.refresh(record)
        return {
            "id": record.id,
            "channel": record.channel,
            "target": record.target,
            "title": record.title,
            "content": record.content,
            "status": record.status,
            "created_at": record.created_at,
        }


def list_notification_logs() -> list[dict]:
    with session_scope() as db:
        return [
            {
                "id": item.id,
                "channel": item.channel,
                "target": item.target,
                "title": item.title,
                "content": item.content,
                "status": item.status,
                "created_at": item.created_at,
            }
            for item in db.scalars(select(NotificationLogDB)).all()
        ]
