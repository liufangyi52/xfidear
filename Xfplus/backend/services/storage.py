import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from backend.database import session_scope
from backend.db_models import AlertDB, BroadcastRecordDB
from backend.models import BroadcastRecord, now_iso
from backend.services.alert_message_builder import ensure_distinct_audience_messages

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
ALERTS_FILE = DATA_DIR / "demo_alerts.json"
BROADCASTS_FILE = DATA_DIR / "broadcast_records.json"
USERS_FILE = DATA_DIR / "users.json"
MESSAGES_FILE = DATA_DIR / "messages.json"
INCIDENTS_FILE = DATA_DIR / "incidents.json"
SHELTERS_FILE = DATA_DIR / "shelters.json"
DISASTER_POINTS_FILE = DATA_DIR / "disaster_points.json"


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _alert_to_dict(alert: AlertDB) -> Dict[str, Any]:
    data = {
        "id": alert.id,
        "title": alert.title,
        "disaster_type": alert.disaster_type,
        "level": alert.level,
        "affected_areas": json.loads(alert.affected_areas or "[]"),
        "started_at": alert.started_at,
        "duration": alert.duration,
        "advice": alert.advice,
        "status": alert.status,
        "data_source_note": alert.data_source_note,
        "audience_messages": json.loads(alert.audience_messages or "{}"),
        "district": alert.district,
        "community": alert.community,
        "created_at": alert.created_at,
        "is_pushed": alert.is_pushed,
        "pushed_at": alert.pushed_at,
    }
    data["audience_messages"] = ensure_distinct_audience_messages(data)
    return data


def list_alerts(is_pushed: Optional[bool] = None, limit: Optional[int] = None, district: Optional[str] = None) -> List[Dict[str, Any]]:
    with session_scope() as db:
        query = select(AlertDB)
        if is_pushed is not None:
            query = query.where(AlertDB.is_pushed == is_pushed)
        if district:
            query = query.where((AlertDB.district.is_(None)) | (AlertDB.district == district))
        alerts = db.scalars(query).all()
        normalized = [_alert_to_dict(alert) for alert in alerts]
    normalized.sort(key=lambda x: x.get("pushed_at") or x.get("created_at") or "", reverse=True)
    return normalized[:limit] if limit else normalized


def get_alert(alert_id: int) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        alert = db.get(AlertDB, alert_id)
        return _alert_to_dict(alert) if alert else None


def save_alert(alert: Dict[str, Any]) -> Dict[str, Any]:
    alert["audience_messages"] = ensure_distinct_audience_messages(alert)
    with session_scope() as db:
        record = AlertDB(
            title=alert["title"],
            disaster_type=alert.get("disaster_type", "暴雨/山洪/滑坡"),
            level=alert.get("level", "橙色"),
            affected_areas=json.dumps(alert.get("affected_areas", []), ensure_ascii=False),
            started_at=alert.get("started_at", ""),
            duration=alert.get("duration", ""),
            advice=alert.get("advice", ""),
            status=alert.get("status", "active"),
            data_source_note=alert.get("data_source_note", "基于公开历史预警资料改编"),
            audience_messages=json.dumps(alert.get("audience_messages", {}), ensure_ascii=False),
            district=alert.get("district"),
            community=alert.get("community"),
            created_at=alert.get("created_at") or now_iso(),
            is_pushed=alert.get("is_pushed", False),
            pushed_at=alert.get("pushed_at"),
        )
        db.add(record)
        db.flush()
        db.refresh(record)
        return _alert_to_dict(record)


def update_alert(alert_id: int, patch: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        alert = db.get(AlertDB, alert_id)
        if not alert:
            return None
        if "audience_messages" in patch:
            current = _alert_to_dict(alert)
            current.update(patch)
            patch["audience_messages"] = ensure_distinct_audience_messages(current)
        for key, value in patch.items():
            if key == "affected_areas":
                value = json.dumps(value, ensure_ascii=False)
            if key == "audience_messages":
                value = json.dumps(value, ensure_ascii=False)
            if hasattr(alert, key):
                setattr(alert, key, value)
        db.flush()
        db.refresh(alert)
        return _alert_to_dict(alert)


def _broadcast_to_dict(record: BroadcastRecordDB) -> Dict[str, Any]:
    return {
        "id": record.id,
        "alert_id": record.alert_id,
        "alert_title": record.alert_title,
        "audience": record.audience,
        "content": record.content,
        "type": record.type,
        "source_type": record.source_type,
        "play_count": record.play_count,
        "created_at": record.created_at,
    }


def list_broadcasts() -> List[Dict[str, Any]]:
    with session_scope() as db:
        records = [_broadcast_to_dict(item) for item in db.scalars(select(BroadcastRecordDB)).all()]
    return sorted(records, key=lambda item: item.get("created_at", ""), reverse=True)


def add_broadcast(
    alert: Dict[str, Any],
    audience: str,
    content: str,
    record_type: str,
    source_type: str = "alert_push",
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    with session_scope() as db:
        record = BroadcastRecordDB(
            alert_id=int(alert.get("id", 0)),
            alert_title=alert.get("title", ""),
            audience=audience,
            content=content,
            type=record_type,
            source_type=source_type,
            created_at=created_at or now_iso(),
        )
        db.add(record)
        db.flush()
        db.refresh(record)
        return BroadcastRecord(**_broadcast_to_dict(record)).model_dump()


def ensure_seed_files() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for path in [BROADCASTS_FILE, USERS_FILE, MESSAGES_FILE, INCIDENTS_FILE]:
        if not path.exists():
            write_json(path, [])
