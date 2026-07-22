from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.models import UserPublic
from backend.permissions import require_admin_role
from backend.services.auth_service import current_user
from backend.services.disaster_points import add_disaster_point, add_shelter, load_disaster_points, load_shelters
from backend.services.storage import now_iso
from backend.services.weather_service import get_current_weather

router = APIRouter(prefix="/api", tags=["meta"])


class RiskPointCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=40)
    scenic_area: str = Field(min_length=1, max_length=120)
    lat: float
    lng: float
    slope: float = Field(ge=0, le=90)
    lithology: str = Field(min_length=1, max_length=120)
    historical_landslide: int = Field(ge=0, le=999)


class ShelterCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    district: str = Field(min_length=2, max_length=40)
    location: str = Field(min_length=1, max_length=120)
    lat: float
    lng: float
    capacity: int = Field(ge=1, le=200000)
    contact: str = Field(min_length=1, max_length=120)


class RiskDataCreate(BaseModel):
    kind: Literal["risk", "shelter"]
    risk: RiskPointCreate | None = None
    shelter: ShelterCreate | None = None


@router.get("/weather/current")
def weather():
    return get_current_weather()


@router.get("/disaster-points")
def disaster_points():
    return [item.model_dump() for item in load_disaster_points()]


@router.get("/shelters")
def shelters():
    return [item.model_dump() for item in load_shelters()]


@router.get("/risk-data")
def risk_data(user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    if user.role == "community_admin":
        return {"disaster_points": [], "shelters": [], "readonly": True}
    district = user.district if user.role == "county_admin" else None
    points = [item.model_dump() for item in load_disaster_points()]
    shelters_data = [item.model_dump() for item in load_shelters()]
    if district:
        points = [item for item in points if item.get("district") == district]
        shelters_data = [
            item
            for item in shelters_data
            if district in item.get("area", "") or item.get("area") in {"武陵源", "天门山", "大峡谷", "黄龙洞", "森林公园"}
        ]
    return {"disaster_points": points, "shelters": shelters_data, "readonly": False}


@router.post("/risk-data")
def create_risk_data(payload: RiskDataCreate, user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    if user.role not in {"city_admin", "county_admin"}:
        raise HTTPException(status_code=403, detail="当前账号无权新增风险数据")

    if payload.kind == "risk":
        if not payload.risk:
            raise HTTPException(status_code=400, detail="缺少风险点字段")
        _assert_risk_data_scope(user, payload.risk.district)
        record = add_disaster_point(
            {
                **payload.risk.model_dump(),
                "source": _manual_source(user),
            }
        )
        return {"success": True, "kind": "risk", "record": record.model_dump()}

    if not payload.shelter:
        raise HTTPException(status_code=400, detail="缺少安置点字段")
    _assert_risk_data_scope(user, payload.shelter.district)
    area = _shelter_area(payload.shelter.district, payload.shelter.location)
    shelter = add_shelter(
        {
            "name": payload.shelter.name,
            "area": area,
            "lat": payload.shelter.lat,
            "lng": payload.shelter.lng,
            "capacity": payload.shelter.capacity,
            "contact": payload.shelter.contact,
            "source": _manual_source(user),
        }
    )
    return {"success": True, "kind": "shelter", "record": shelter.model_dump()}


def _assert_risk_data_scope(user: UserPublic, district: str) -> None:
    if user.role == "city_admin":
        return
    if user.role == "county_admin" and user.district == district:
        return
    raise HTTPException(status_code=403, detail="区县级账号只能新增本区县范围内的风险数据")


def _manual_source(user: UserPublic) -> str:
    return f"管理端录入 · {user.username} · {now_iso()}"


def _shelter_area(district: str, location: str) -> str:
    cleaned = location.strip()
    if cleaned.startswith(district):
        return cleaned
    return f"{district} · {cleaned}"
