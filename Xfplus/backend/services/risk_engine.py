from math import asin, cos, radians, sin, sqrt
from typing import Any, Dict, List

from backend.models import DisasterPoint, Shelter
from backend.services.disaster_points import load_disaster_points, load_shelters
from backend.services.weather_service import get_current_weather


def calculate_risk_level(rainfall_24h: float, slope: float, historical_landslide: int) -> str:
    if rainfall_24h > 100 or (rainfall_24h > 50 and slope > 30) or historical_landslide >= 3:
        return "高"
    if rainfall_24h > 50 or (rainfall_24h > 25 and slope > 25) or historical_landslide >= 2:
        return "中"
    if rainfall_24h > 10:
        return "低"
    return "待观察"


def warning_color(level: str) -> str:
    return {"高": "red", "中": "orange", "低": "yellow"}.get(level, "blue")


def action_for(level: str) -> str:
    return {
        "高": "立即加强巡查，暂停高风险游线，组织临坡住户和滞留游客转移。",
        "中": "密切监测雨情和边坡变形，准备转移物资和安置点。",
        "低": "保持关注，提醒游客远离溪谷、陡坡和落石路段。",
        "待观察": "维持常态巡查，关注后续降雨变化。",
    }[level]


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371
    d_lat = radians(lat2 - lat1)
    d_lng = radians(lng2 - lng1)
    a = sin(d_lat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lng / 2) ** 2
    return 2 * radius * asin(sqrt(a))


def nearest_shelter(point: DisasterPoint, shelters: List[Shelter]) -> Dict[str, Any]:
    ranked = sorted(shelters, key=lambda shelter: haversine_km(point.lat, point.lng, shelter.lat, shelter.lng))
    shelter = ranked[0]
    distance = haversine_km(point.lat, point.lng, shelter.lat, shelter.lng)
    return {
        "id": shelter.id,
        "name": shelter.name,
        "lat": shelter.lat,
        "lng": shelter.lng,
        "capacity": shelter.capacity,
        "distance_km": round(distance, 2),
    }


def enrich_risk_point(point: DisasterPoint, rainfall_24h: float, shelters: List[Shelter]) -> Dict[str, Any]:
    level = calculate_risk_level(rainfall_24h, point.slope, point.historical_landslide)
    risk_score = min(100, round(rainfall_24h * 0.55 + point.slope * 0.85 + point.historical_landslide * 9))
    return {
        **point.model_dump(),
        "risk_level": level,
        "warning_color": warning_color(level),
        "risk_score": risk_score,
        "heat_weight": round(max(0.15, risk_score / 100), 2),
        "action": action_for(level),
        "nearby_shelter": nearest_shelter(point, shelters),
        "guide_target": "/alerts/1" if level in {"高", "中"} else "/app",
    }


def current_risk(district: str | None = None) -> Dict[str, Any]:
    weather = get_current_weather()
    shelters = load_shelters()
    points = load_disaster_points()
    if district:
        points = [point for point in points if point.district == district]
    risks = [enrich_risk_point(point, weather["rainfall_24h"], shelters) for point in points]
    return {"weather": weather, "points": risks}
