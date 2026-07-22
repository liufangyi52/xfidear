import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from backend.database import session_scope
from backend.db_models import IncidentDB
from backend.models import Incident, IncidentCreate, UserPublic, now_iso
from backend.services.disaster_points import load_shelters
from backend.services.risk_engine import haversine_km

TYPE_KEYWORDS = {
    "flood": ["暴雨", "积水", "涨水", "山洪", "内涝", "水位"],
    "landslide": ["滑坡", "塌方", "落石", "泥石流", "崩塌"],
    "road": ["道路", "中断", "堵塞", "桥", "交通", "绕行"],
    "medical": ["受伤", "昏迷", "急救", "送医", "救护"],
    "shelter": ["安置", "转移", "避险", "疏散"],
    "sos": ["求助", "救命", "被困", "危险", "sos", "SOS"],
}

SEVERITY_SCORE = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def classify_incident(description: str) -> str:
    for incident_type, keywords in TYPE_KEYWORDS.items():
        if any(keyword in description for keyword in keywords):
            return incident_type
    return "other"


def infer_severity(incident_type: str, description: str) -> str:
    if incident_type == "sos" or any(word in description for word in ["被困", "救命", "多人", "滞留", "伤员"]):
        return "critical"
    if incident_type in {"landslide", "road"}:
        return "high"
    if incident_type in {"flood", "medical", "shelter"}:
        return "medium"
    return "low"


def nearest_shelter_for(lat: float, lng: float) -> Optional[Dict[str, Any]]:
    shelters = load_shelters()
    if not shelters:
        return None
    shelter = min(shelters, key=lambda item: haversine_km(lat, lng, item.lat, item.lng))
    return {
        "id": shelter.id,
        "name": shelter.name,
        "area": shelter.area,
        "lat": shelter.lat,
        "lng": shelter.lng,
        "capacity": shelter.capacity,
        "distance_km": round(haversine_km(lat, lng, shelter.lat, shelter.lng), 2),
    }


def _to_dict(incident: IncidentDB) -> Dict[str, Any]:
    return {
        "id": incident.id,
        "type": incident.type,
        "description": incident.description,
        "lat": incident.lat,
        "lng": incident.lng,
        "district": incident.district,
        "community": incident.community,
        "scenic_area": incident.scenic_area,
        "severity": incident.severity,
        "status": incident.status,
        "reporter_role": incident.reporter_role,
        "reporter_id": incident.reporter_id,
        "nearest_shelter": json.loads(incident.nearest_shelter) if incident.nearest_shelter else None,
        "source_title": incident.source_title or "",
        "source_org": incident.source_org or "",
        "source_url": incident.source_url or "",
        "source_date": incident.source_date or "",
        "workflow_steps": json.loads(incident.workflow_steps) if incident.workflow_steps else [],
        "need_review": bool(getattr(incident, "need_review", False)),
        "is_demo": incident.is_demo,
        "created_at": incident.created_at,
        "resolved_at": incident.resolved_at,
    }


def _apply_time_range(query, time_range: Optional[str]):
    if not time_range or time_range == "all":
        return query
    hours = 24 if time_range == "24h" else 24 * 7 if time_range == "7d" else None
    if not hours:
        return query
    since = (datetime.now() - timedelta(hours=hours)).isoformat(timespec="seconds")
    return query.where(IncidentDB.created_at >= since)


def list_incidents(
    user: Optional[UserPublic] = None,
    status: Optional[str] = None,
    incident_type: Optional[str] = None,
    time_range: Optional[str] = None,
    mine_only: bool = False,
) -> List[Dict[str, Any]]:
    with session_scope() as db:
        query = select(IncidentDB)
        if status:
            query = query.where(IncidentDB.status == status)
        if incident_type:
            query = query.where(IncidentDB.type == incident_type)
        query = _apply_time_range(query, time_range)

        if user:
            if mine_only:
                query = query.where(IncidentDB.reporter_id == user.id)
            if user.role in {"county_admin", "resident"} and user.district:
                query = query.where(IncidentDB.district == user.district)
            elif user.role == "community_admin":
                if user.district:
                    query = query.where(IncidentDB.district == user.district)
                if user.community:
                    query = query.where((IncidentDB.community.is_(None)) | (IncidentDB.community == user.community))
            # 游客可看匿名化全市事件，市级可看全市事件。
        incidents = [_to_dict(item) for item in db.scalars(query).all()]

    if user and user.role == "tourist":
        for item in incidents:
            item["reporter_id"] = None
            item["community"] = None
    return sorted(
        incidents,
        key=lambda item: (item.get("type") == "sos", item.get("created_at", ""), item.get("id", 0)),
        reverse=True,
    )


def get_incident(incident_id: int) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        incident = db.get(IncidentDB, incident_id)
        return _to_dict(incident) if incident else None


def create_incident(payload: IncidentCreate, user: UserPublic) -> Dict[str, Any]:
    data = payload.model_dump()
    if data["type"] == "other":
        data["type"] = classify_incident(data["description"])
    data["severity"] = infer_severity(data["type"], data["description"])
    data["district"] = data.get("district") or user.district or _infer_district(data["lat"], data["lng"])
    data["community"] = None if user.role == "tourist" else data.get("community") or user.community
    data["scenic_area"] = data.get("scenic_area") or _infer_scenic_area(data["description"], data["district"])
    nearest = nearest_shelter_for(data["lat"], data["lng"])
    with session_scope() as db:
        incident = IncidentDB(
            type=data["type"],
            description=data["description"],
            lat=data["lat"],
            lng=data["lng"],
            district=data["district"],
            community=data["community"],
            scenic_area=data["scenic_area"],
            severity=data["severity"],
            status=data.get("status", "pending"),
            reporter_role=user.role,
            reporter_id=user.id,
            nearest_shelter=json.dumps(nearest, ensure_ascii=False) if nearest else None,
            source_title=data.get("source_title", ""),
            source_org=data.get("source_org", ""),
            source_url=data.get("source_url", ""),
            source_date=data.get("source_date", ""),
            workflow_steps=json.dumps(data.get("workflow_steps", []), ensure_ascii=False),
            need_review=user.role == "tourist",
            is_demo=data.get("is_demo", False),
            created_at=now_iso(),
        )
        db.add(incident)
        db.flush()
        db.refresh(incident)
        return Incident(**_to_dict(incident)).model_dump()


def update_incident_status(incident_id: int, status: str) -> Optional[Dict[str, Any]]:
    with session_scope() as db:
        incident = db.get(IncidentDB, incident_id)
        if not incident:
            return None
        incident.status = status
        if status == "resolved":
            incident.resolved_at = now_iso()
        db.flush()
        db.refresh(incident)
        return _to_dict(incident)


def create_demo_incidents(user: UserPublic) -> List[Dict[str, Any]]:
    samples = [
        IncidentCreate(
            type="flood",
            description="金鞭溪水位上涨，有游客滞留在步道附近，请求协助疏导。",
            lat=29.3472,
            lng=110.5587,
            district="武陵源区",
            community="标志门社区",
            scenic_area="金鞭溪",
            is_demo=True,
        ),
        IncidentCreate(
            type="road",
            description="天门山索道站周边道路短时拥堵，部分游客等待疏导。",
            lat=29.1167,
            lng=110.4759,
            district="永定区",
            scenic_area="天门山",
            is_demo=True,
        ),
        IncidentCreate(
            type="landslide",
            description="大峡谷玻璃桥入口道路出现落石，需要临时绕行。",
            lat=29.3939,
            lng=110.6938,
            district="慈利县",
            scenic_area="张家界大峡谷",
            is_demo=True,
        ),
        IncidentCreate(
            type="sos",
            description="游客在黄龙洞出口附近摔伤无法行走，请求 SOS 救援。",
            lat=29.3679,
            lng=110.6172,
            district="武陵源区",
            community="标志门社区",
            scenic_area="黄龙洞",
            is_demo=True,
        ),
    ]
    return [create_incident(sample, user) for sample in samples]


def incident_stats(incidents: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "total": len(incidents),
        "pending": len([item for item in incidents if item.get("status") == "pending"]),
        "responding": len([item for item in incidents if item.get("status") == "responding"]),
        "resolved": len([item for item in incidents if item.get("status") == "resolved"]),
        "critical": len([item for item in incidents if item.get("severity") == "critical"]),
        "need_review": len([item for item in incidents if item.get("need_review")]),
    }


def incident_heat_points(incidents: List[Dict[str, Any]]) -> List[List[float]]:
    points = []
    for item in incidents:
        severity_weight = SEVERITY_SCORE.get(item.get("severity", "low"), 1) / 4
        status_weight = 1 if item.get("status") != "resolved" else 0.35
        points.append([item["lat"], item["lng"], round(severity_weight * status_weight, 2)])
    return points


def _infer_district(lat: float, lng: float) -> str:
    if lng > 110.65:
        return "慈利县"
    if lat > 29.5:
        return "桑植县"
    if lat > 29.25:
        return "武陵源区"
    return "永定区"


def _infer_scenic_area(description: str, district: Optional[str]) -> str:
    if "金鞭溪" in description:
        return "金鞭溪"
    if "天门山" in description or district == "永定区":
        return "天门山"
    if "大峡谷" in description or district == "慈利县":
        return "张家界大峡谷"
    if "黄龙洞" in description:
        return "黄龙洞"
    return district or "张家界"
