from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from backend.database import session_scope
from backend.db_models import UserDB
from backend.models import Alert, AlertCreate, UserPublic, now_iso
from backend.permissions import assert_scope_access, require_admin_role
from backend.services.auth_service import current_user
from backend.services.message_service import create_system_message
from backend.services.storage import add_broadcast, get_alert, list_alerts, save_alert, update_alert

router = APIRouter(prefix="/api/alerts", tags=["alerts"])

PUBLIC_AUDIENCE_ROLE = {
    "resident": "resident",
    "tourist": "tourist",
}
AUDIENCE_MESSAGE_KEYS = ("county_admin", "resident", "tourist", "village_officer", "scenic_manager")
ZJJ_DISTRICTS = ("永定区", "武陵源区", "慈利县", "桑植县")
CITY_PUSH_AUDIENCES = (("county_admin", "county_admin", "区县管理"),)
COUNTY_PUSH_AUDIENCES = (
    ("resident", "resident", "居民"),
    ("tourist", "tourist", "游客"),
)
AUDIENCE_LABELS = {
    "county_admin": "区县应急管理",
    "resident": "居民",
    "tourist": "游客",
    "village_officer": "村干部",
    "scenic_manager": "景区管理",
}


def _alert_for_user(alert: dict, user: UserPublic) -> dict:
    data = dict(alert)
    audience_key = PUBLIC_AUDIENCE_ROLE.get(user.role)
    if not audience_key:
        return data

    messages = data.get("audience_messages") or {}
    visible_text = messages.get(audience_key) or data.get("advice") or ""
    data["audience_messages"] = {
        key: visible_text if key == audience_key else ""
        for key in AUDIENCE_MESSAGE_KEYS
    }
    return data


def _target_districts(alert: dict, user: UserPublic) -> list[str | None]:
    if user.role != "city_admin":
        return [user.district]
    if alert.get("district"):
        return [alert.get("district")]
    areas_text = "、".join(str(item) for item in alert.get("affected_areas") or [])
    matched = [district for district in ZJJ_DISTRICTS if district in areas_text]
    return matched or [None]


def _message_for_audience(alert: dict, message_key: str) -> str:
    messages = alert.get("audience_messages") or {}
    return messages.get(message_key) or alert.get("advice") or alert.get("title", "")


def _broadcast_content(alert: dict) -> str:
    areas = "、".join(str(item) for item in alert.get("affected_areas") or [] if str(item).strip())
    parts = [
        f"【{alert.get('title', '预警通知')}】",
        f"预警等级：{alert.get('level') or '当前'}。",
    ]
    if areas:
        parts.append(f"影响区域：{areas}。")
    if alert.get("duration"):
        parts.append(f"持续时间：{alert.get('duration')}。")
    if alert.get("advice"):
        parts.append(f"处置要求：{alert.get('advice')}。")

    messages = alert.get("audience_messages") or {}
    for key in AUDIENCE_MESSAGE_KEYS:
        text = str(messages.get(key) or "").strip()
        if text:
            parts.append(f"{AUDIENCE_LABELS.get(key, key)}通知：{text}")
    return "\n".join(parts)


def _push_audience_messages(alert: dict, user: UserPublic, source_type: str) -> list[dict]:
    sent = []
    for recipient in _target_recipients(alert, user):
        role, message_key, audience_label = _audience_for_role(user, recipient.role)
        content = _message_for_audience(alert, message_key)
        target_district = recipient.district or (user.district if user.role != "city_admin" else None)
        message = create_system_message(
            user,
            title=f"新预警：{alert['title']}｜{audience_label}",
            content=content,
            target_roles=[role],
            target_district=target_district,
            target_community=recipient.community if role == "community_admin" else None,
            target_user_id=recipient.id,
            source_type=source_type,
            related_id=int(alert["id"]),
        )
        sent.append(message.model_dump())
    return sent


def _push_audiences_for_user(user: UserPublic) -> tuple[tuple[str, str, str], ...]:
    if user.role == "city_admin":
        return CITY_PUSH_AUDIENCES
    if user.role == "county_admin":
        return COUNTY_PUSH_AUDIENCES
    return ()


def _audience_for_role(user: UserPublic, role: str) -> tuple[str, str, str]:
    for item in _push_audiences_for_user(user):
        if item[0] == role:
            return item
    raise HTTPException(status_code=403, detail="当前账号无权向该角色推送预警")


def _target_recipients(alert: dict, user: UserPublic) -> list[UserPublic]:
    allowed_roles = {role for role, _, _ in _push_audiences_for_user(user)}
    if not allowed_roles:
        raise HTTPException(status_code=403, detail="当前账号无预警推送权限")
    districts = _target_districts(alert, user)
    city_wide = districts == [None]

    with session_scope() as db:
        records = [
            UserPublic(
                id=int(record.id),
                username=record.username,
                role=record.role,
                district=record.district,
                community=record.community,
            )
            for record in db.scalars(select(UserDB).where(UserDB.role.in_(allowed_roles))).all()
        ]

    recipients = []
    seen_ids = set()
    for public in records:
        if public.id in seen_ids:
            continue
        if user.role == "city_admin":
            if public.role != "county_admin":
                continue
            if not city_wide and public.district not in districts:
                continue
        elif user.role == "county_admin":
            if public.role not in {"resident", "tourist"}:
                continue
            if public.role == "resident" and public.district != user.district:
                continue
            if public.role == "tourist" and public.district not in {None, user.district}:
                continue

        seen_ids.add(public.id)
        recipients.append(public)
    return recipients


@router.get("")
def alerts(
    is_pushed: Optional[bool] = Query(None),
    limit: Optional[int] = Query(None),
    user: UserPublic = Depends(current_user),
):
    # 居民、游客可查看全市公开预警；区县/社区管理端自动包含本区县和全市预警。
    district = None if user.role in {"city_admin", "resident", "tourist"} else user.district
    alerts = list_alerts(is_pushed=is_pushed, limit=limit, district=district)
    return [_alert_for_user(alert, user) for alert in alerts]


@router.get("/{alert_id}")
def alert_detail(alert_id: int, user: UserPublic = Depends(current_user)):
    alert = get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if user.role not in {"city_admin", "resident", "tourist"} and alert.get("district") and user.district != alert.get("district"):
        raise HTTPException(status_code=403, detail="Alert is outside your scope")
    return _alert_for_user(alert, user)


@router.post("", response_model=Alert)
def create_alert(payload: AlertCreate, user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    if user.role == "community_admin":
        raise HTTPException(status_code=403, detail="社区/村部干部只能转发上级预警，不能创建新预警")
    data = payload.model_dump()
    data["district"] = data.get("district") or (None if user.role == "city_admin" else user.district)
    data["community"] = None
    assert_scope_access(user, data.get("district"), data.get("community"))
    return save_alert(data)


@router.put("/{alert_id}", response_model=Alert)
def edit_alert(alert_id: int, payload: AlertCreate, user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    if user.role == "community_admin":
        raise HTTPException(status_code=403, detail="社区/村部干部只能转发上级预警，不能编辑预警")
    alert = get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    assert_scope_access(user, alert.get("district"), alert.get("community"))
    data = payload.model_dump()
    data["district"] = data.get("district") or alert.get("district")
    data["community"] = None
    assert_scope_access(user, data.get("district"), data.get("community"))
    updated = update_alert(alert_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Alert not found")
    return updated


@router.post("/{alert_id}/push")
def push_alert(alert_id: int, user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    alert = get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    assert_scope_access(user, alert.get("district"), alert.get("community"))

    pushed_at = now_iso()
    updated = update_alert(alert_id, {"is_pushed": True, "pushed_at": pushed_at})
    if user.role == "city_admin":
        audience = "区县级应急管理人员"
        record_type = "市级管理端推送"
    else:
        audience = "本区县居民与游客"
        record_type = "区县端推送"
    record = add_broadcast(
        updated,
        audience,
        _broadcast_content(updated),
        record_type,
        source_type="alert_push",
        created_at=pushed_at,
    )
    messages = _push_audience_messages(updated, user, "alert_push")
    return {"success": True, "alert": updated, "broadcast": record, "messages": messages, "pushed_at": pushed_at}


@router.post("/{alert_id}/unpush")
def unpush_alert(alert_id: int, user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    alert = get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    assert_scope_access(user, alert.get("district"), alert.get("community"))
    updated = update_alert(alert_id, {"is_pushed": False, "pushed_at": None})
    return {"success": True, "alert": updated}


@router.post("/{alert_id}/forward")
def forward_alert(alert_id: int, user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    alert = get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    assert_scope_access(user, alert.get("district"), alert.get("community"))
    content = alert.get("audience_messages", {}).get("resident") or alert.get("advice") or alert["title"]
    message = create_system_message(
        user,
        title=f"转发上级预警：{alert['title']}",
        content=content,
        target_roles=["resident", "tourist"],
        target_district=user.district if user.role != "city_admin" else alert.get("district"),
        target_community=user.community if user.role == "community_admin" else None,
        source_type="alert_forward",
        related_id=alert_id,
    )
    return {"success": True, "message": message.model_dump()}
