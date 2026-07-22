import json
from typing import Any, Dict, List

from fastapi import HTTPException
from sqlalchemy import select

from backend.database import session_scope
from backend.db_models import MessageDB, UserDB
from backend.models import DispatchMessage, MessageCreate, Role, UserPublic, now_iso
from backend.services.realtime_service import notification_hub

ROLE_PRIORITY = {
    "city_admin": "city",
    "county_admin": "county",
    "community_admin": "community",
    "resident": "normal",
    "tourist": "normal",
}


def _allowed_targets(sender: UserPublic) -> set[Role]:
    if sender.role == "city_admin":
        return {"county_admin", "community_admin", "resident", "tourist"}
    if sender.role == "county_admin":
        return {"community_admin", "resident", "tourist"}
    if sender.role == "community_admin":
        return {"community_admin", "resident", "tourist"}
    return set()


def _in_scope(sender: UserPublic, payload: MessageCreate) -> bool:
    if sender.role == "city_admin":
        return True
    if sender.role == "county_admin":
        return payload.target_district == sender.district
    if sender.role == "community_admin":
        return payload.target_district == sender.district and payload.target_community in {sender.community, None}
    return False


def _is_public_suggestion(message: Dict[str, Any]) -> bool:
    return message.get("source_type") == "public_suggestion"


def message_visible_to_user(user: UserPublic, message: Dict[str, Any], district: str | None = None, community: str | None = None) -> bool:
    public_suggestion = _is_public_suggestion(message)
    if user.role == "city_admin" and public_suggestion:
        return True
    if user.role == "county_admin" and public_suggestion:
        return message.get("target_district") == user.district
    if public_suggestion and message.get("sender_id") == user.id:
        return True
    if message.get("target_user_id") and message["target_user_id"] != user.id:
        return False
    if user.role not in message["target_roles"]:
        return False
    if message.get("target_district") and user.district and message["target_district"] != user.district:
        return False
    if message.get("target_community") and user.community and message["target_community"] != user.community:
        return False
    if district and message.get("target_district") not in {None, district}:
        return False
    if community and message.get("target_community") not in {None, community}:
        return False
    return True


def _to_dict(message: MessageDB) -> Dict[str, Any]:
    return {
        "id": message.id,
        "title": message.title,
        "content": message.content,
        "target_roles": json.loads(message.target_roles or "[]"),
        "target_district": message.target_district,
        "target_community": message.target_community,
        "target_user_id": message.target_user_id,
        "sender_id": message.sender_id,
        "sender_role": message.sender_role,
        "priority": message.priority,
        "source_type": message.source_type,
        "related_id": message.related_id,
        "parent_id": message.parent_id,
        "status": message.status or "sent",
        "reply_content": message.reply_content or "",
        "review_note": message.review_note or "",
        "reviewed_by": message.reviewed_by,
        "reviewed_at": message.reviewed_at,
        "attachments": json.loads(message.attachments or "[]"),
        "created_at": message.created_at,
    }


def create_message(sender: UserPublic, payload: MessageCreate) -> DispatchMessage:
    allowed = _allowed_targets(sender)
    if not allowed or any(role not in allowed for role in payload.target_roles):
        raise HTTPException(status_code=403, detail="Target role is outside your dispatch permission")
    if not _in_scope(sender, payload):
        raise HTTPException(status_code=403, detail="Target area is outside your dispatch permission")

    with session_scope() as db:
        message = MessageDB(
            title=payload.title,
            content=payload.content,
            target_roles=json.dumps(payload.target_roles, ensure_ascii=False),
            target_district=payload.target_district,
            target_community=payload.target_community,
            target_user_id=payload.target_user_id,
            sender_id=sender.id,
            sender_role=sender.role,
            priority=ROLE_PRIORITY[sender.role],
            source_type=payload.source_type,
            related_id=payload.related_id,
            parent_id=payload.parent_id,
            status="sent",
            created_at=now_iso(),
        )
        db.add(message)
        db.flush()
        db.refresh(message)
        created = DispatchMessage(**_to_dict(message))
    _publish_message(created.model_dump())
    return created


def create_system_message(
    sender: UserPublic,
    title: str,
    content: str,
    target_roles: List[Role],
    target_district: str | None = None,
    target_community: str | None = None,
    target_user_id: int | None = None,
    source_type: str = "system",
    related_id: int | None = None,
) -> DispatchMessage:
    return create_message(
        sender,
        MessageCreate(
            title=title,
            content=content,
            target_roles=target_roles,
            target_district=target_district,
            target_community=target_community,
            target_user_id=target_user_id,
            source_type=source_type,
            related_id=related_id,
        ),
    )


def visible_messages(user: UserPublic, district: str | None = None, community: str | None = None) -> List[Dict[str, Any]]:
    with session_scope() as db:
        messages = [_to_dict(item) for item in db.scalars(select(MessageDB)).all()]
    public_suggestion_ids = {message["id"] for message in messages if _is_public_suggestion(message)}
    visible = []
    for message in messages:
        if user.role == "city_admin" and (
            _is_public_suggestion(message) or message.get("parent_id") in public_suggestion_ids
        ):
            visible.append(message)
            continue
        if user.role == "county_admin" and (
            _is_public_suggestion(message) or message.get("parent_id") in public_suggestion_ids
        ):
            if message.get("target_district") == user.district:
                visible.append(message)
            continue
        if _is_public_suggestion(message) and message.get("sender_id") == user.id:
            visible.append(message)
            continue
        if not message_visible_to_user(user, message, district=district, community=community):
            continue
        visible.append(message)
    return sorted(visible, key=lambda item: item["created_at"], reverse=True)


def all_messages() -> List[Dict[str, Any]]:
    with session_scope() as db:
        return [_to_dict(item) for item in db.scalars(select(MessageDB)).all()]


def create_public_suggestion(sender: UserPublic, title: str, content: str, district: str | None = None, community: str | None = None) -> DispatchMessage:
    if sender.role not in {"resident", "tourist"}:
        raise HTTPException(status_code=403, detail="Only residents and tourists can submit suggestions")
    with session_scope() as db:
        message = MessageDB(
            title=title,
            content=content,
            target_roles=json.dumps(["city_admin", "county_admin"], ensure_ascii=False),
            target_district=district or sender.district,
            target_community=community or sender.community,
            target_user_id=None,
            sender_id=sender.id,
            sender_role=sender.role,
            priority="normal",
            source_type="public_suggestion",
            status="pending_review",
            created_at=now_iso(),
        )
        db.add(message)
        db.flush()
        db.refresh(message)
        created = DispatchMessage(**_to_dict(message))
    _publish_message(created.model_dump())
    return created


def update_message_attachments(message_id: int, attachments: List[Dict[str, Any]]) -> DispatchMessage:
    with session_scope() as db:
        message = db.get(MessageDB, message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        message.attachments = json.dumps(attachments, ensure_ascii=False)
        db.flush()
        db.refresh(message)
        return DispatchMessage(**_to_dict(message))


def get_visible_message(user: UserPublic, message_id: int) -> Dict[str, Any]:
    for message in visible_messages(user):
        if message["id"] == message_id:
            return message
    raise HTTPException(status_code=404, detail="Message not found")


def cancel_public_suggestion(sender: UserPublic, message_id: int) -> DispatchMessage:
    with session_scope() as db:
        message = db.get(MessageDB, message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        if message.source_type != "public_suggestion":
            raise HTTPException(status_code=400, detail="Only public suggestions can be cancelled")
        if message.sender_id != sender.id:
            raise HTTPException(status_code=403, detail="Message is outside your permission")
        if message.status not in {"pending", "pending_review"}:
            raise HTTPException(status_code=409, detail="Message can no longer be cancelled")
        message.status = "cancelled"
        message.review_note = "Cancelled by sender"
        message.reviewed_at = now_iso()
        db.flush()
        db.refresh(message)
        return DispatchMessage(**_to_dict(message))


def _reviewer_can_handle(reviewer: UserPublic, message: MessageDB) -> bool:
    if reviewer.role == "city_admin":
        return True
    return reviewer.role == "county_admin" and message.target_district == reviewer.district


def review_message(reviewer: UserPublic, message_id: int, status: str, reply_content: str = "", review_note: str = "") -> DispatchMessage:
    if reviewer.role not in {"city_admin", "county_admin"}:
        raise HTTPException(status_code=403, detail="Only city or county admin can review public suggestions")
    with session_scope() as db:
        message = db.get(MessageDB, message_id)
        if not message:
            raise HTTPException(status_code=404, detail="Message not found")
        if message.source_type != "public_suggestion":
            raise HTTPException(status_code=400, detail="Only public suggestions can be reviewed")
        if not _reviewer_can_handle(reviewer, message):
            raise HTTPException(status_code=403, detail="Message is outside your district permission")
        message.status = status
        message.reply_content = reply_content
        message.review_note = review_note
        message.reviewed_by = reviewer.id
        message.reviewed_at = now_iso()
        db.flush()
        db.refresh(message)
        reviewed = DispatchMessage(**_to_dict(message))

    if reply_content.strip():
        create_message(
            reviewer,
            MessageCreate(
                title=f"建议反馈：{reviewed.title}",
                content=reply_content.strip(),
                target_roles=[reviewed.sender_role],
                target_district=reviewed.target_district,
                target_community=reviewed.target_community,
                target_user_id=reviewed.sender_id,
                source_type="suggestion_reply",
                parent_id=reviewed.id,
            ),
        )
    return reviewed


def forward_rectification(reviewer: UserPublic, source_id: int, payload: MessageCreate) -> DispatchMessage:
    if reviewer.role not in {"city_admin", "county_admin"}:
        raise HTTPException(status_code=403, detail="Only city or county admin can dispatch rectification tasks")
    with session_scope() as db:
        source = db.get(MessageDB, source_id)
        if not source:
            raise HTTPException(status_code=404, detail="Message not found")
        if source.source_type != "public_suggestion":
            raise HTTPException(status_code=400, detail="Only public suggestions can be forwarded")
        if not _reviewer_can_handle(reviewer, source):
            raise HTTPException(status_code=403, detail="Message is outside your district permission")
        payload.target_district = payload.target_district or source.target_district
        source.status = "forwarded"
        source.reviewed_by = reviewer.id
        source.reviewed_at = now_iso()
    payload.source_type = "rectification_task"
    payload.parent_id = source_id
    return create_message(reviewer, payload)


def _publish_message(message: Dict[str, Any]) -> None:
    with session_scope() as db:
        users = [user for user in db.scalars(select(UserDB)).all()]

    user_ids = []
    for record in users:
        public_user = UserPublic(
            id=int(record.id),
            username=record.username,
            role=record.role,
            district=record.district,
            community=record.community,
        )
        if public_user.role == "city_admin" and _is_public_suggestion(message):
            user_ids.append(public_user.id)
            continue
        if public_user.role == "county_admin" and _is_public_suggestion(message) and message.get("target_district") == public_user.district:
            user_ids.append(public_user.id)
            continue
        if _is_public_suggestion(message) and message.get("sender_id") == public_user.id:
            user_ids.append(public_user.id)
            continue
        if message_visible_to_user(public_user, message):
            user_ids.append(public_user.id)

    notification_hub.publish_message(
        sorted(set(user_ids)),
        {
            "type": "message",
            "message": message,
        },
    )
