from collections import Counter
from typing import Optional

from fastapi import APIRouter, Depends, Query

from backend.models import UserPublic
from backend.permissions import require_admin_role
from backend.services.auth_service import current_user
from backend.services.disaster_points import load_shelters
from backend.services.incident_service import incident_heat_points, incident_stats, list_incidents
from backend.services.message_service import all_messages, visible_messages
from backend.services.risk_engine import current_risk
from backend.services.storage import list_alerts

router = APIRouter(prefix="/api/command", tags=["command"])

DEMO_COUNTY_DISTRICTS = {"永定区", "武陵源区", "桑植县", "慈利县"}


def _clean_scope_value(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _effective_scope(
    user: UserPublic,
    active_district: str | None = None,
    active_community: str | None = None,
) -> tuple[str | None, str | None]:
    district = _clean_scope_value(active_district)
    community = _clean_scope_value(active_community)

    if user.role == "city_admin":
        return district, community

    if user.role == "county_admin":
        selected = district or user.district
        if district and district not in DEMO_COUNTY_DISTRICTS and district != user.district:
            selected = user.district
        return selected, None

    if user.role == "community_admin":
        selected = district or user.district
        if district and district not in DEMO_COUNTY_DISTRICTS and district != user.district:
            selected = user.district
        return selected, community or user.community

    return user.district, user.community


def _scoped_shelters(district: str | None) -> list[dict]:
    shelters = [item.model_dump() for item in load_shelters()]
    if not district:
        return shelters
    return [item for item in shelters if district in item["area"] or item["area"] == district]


def _scoped_alerts(user: UserPublic, district: str | None, community: str | None) -> list[dict]:
    alert_district = district if user.role != "city_admin" or district else None
    alerts = list_alerts(district=alert_district)
    if user.role != "city_admin" and district:
        alerts = [item for item in alerts if item.get("district") == district]
    if user.role == "community_admin" and community:
        alerts = [item for item in alerts if not item.get("community") or item.get("community") == community]
    return alerts


@router.get("/overview")
def overview(
    time_range: Optional[str] = Query(default="24h"),
    active_district: Optional[str] = Query(default=None),
    active_community: Optional[str] = Query(default=None),
    user: UserPublic = Depends(current_user),
):
    require_admin_role(user)
    district, community = _effective_scope(user, active_district, active_community)
    scope_user = user.model_copy(update={"district": district, "community": community})

    risk = current_risk(district if user.role != "city_admin" or district else None)
    shelters = _scoped_shelters(district)
    incidents = list_incidents(user=scope_user, time_range=time_range)
    if district:
        incidents = [item for item in incidents if item.get("district") == district]
    if community and user.role == "community_admin":
        incidents = [item for item in incidents if not item.get("community") or item.get("community") == community]

    district_counts = Counter(point["district"] for point in risk["points"])
    inbox = visible_messages(scope_user)
    screen_messages = all_messages() if user.role == "city_admin" and not district else inbox
    screen_messages = sorted(screen_messages, key=lambda item: item.get("created_at") or "", reverse=True)
    all_message_count = len(screen_messages)
    high_points = [point for point in risk["points"] if point.get("warning_color") in {"red", "orange"}]
    heat_points = [[point["lat"], point["lng"], point["heat_weight"]] for point in risk["points"]]
    event_heat_points = incident_heat_points(incidents)
    alerts = _scoped_alerts(user, district, community)

    return {
        "user": scope_user.model_dump(),
        "scope": {
            "level": user.role,
            "district": district,
            "community": community,
            "time_range": time_range,
            "source": "login_selection" if active_district or active_community else "user_profile",
        },
        "weather": risk["weather"],
        "risk_points": risk["points"],
        "shelters": shelters,
        "heat_points": heat_points,
        "incident_heat_points": event_heat_points,
        "incidents": incidents,
        "incident_stats": incident_stats(incidents),
        "stats": {
            "alert_count": len(alerts),
            "risk_point_count": len(risk["points"]),
            "high_risk_count": len(high_points),
            "shelter_capacity": sum(item["capacity"] for item in shelters),
            "message_count": all_message_count,
            "inbox_count": len(inbox),
            "incident_count": len(incidents),
            "pending_incident_count": len([item for item in incidents if item.get("status") == "pending"]),
        },
        "district_metrics": [{"district": key, "risk_points": value} for key, value in district_counts.items()],
        "messages": screen_messages,
    }
