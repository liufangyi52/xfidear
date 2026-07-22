from typing import Any, List
from uuid import uuid4

from sqlalchemy import select

from backend.database import session_scope
from backend.db_models import ShelterDB
from backend.models import DisasterPoint, Shelter
from backend.services.storage import DISASTER_POINTS_FILE, SHELTERS_FILE, read_json, write_json


def load_disaster_points() -> List[DisasterPoint]:
    return [DisasterPoint(**item) for item in read_json(DISASTER_POINTS_FILE, [])]


def load_shelters() -> List[Shelter]:
    with session_scope() as db:
        rows = db.scalars(select(ShelterDB)).all()
        if rows:
            return [
                Shelter(
                    id=item.id,
                    name=item.name,
                    area=item.area,
                    lat=item.lat,
                    lng=item.lng,
                    capacity=item.capacity,
                    contact=item.contact,
                    source=item.source,
                )
                for item in rows
            ]
    return [Shelter(**item) for item in read_json(SHELTERS_FILE, [])]


def add_disaster_point(payload: dict[str, Any]) -> DisasterPoint:
    records = read_json(DISASTER_POINTS_FILE, [])
    record = {
        "id": f"risk-{uuid4().hex[:10]}",
        "name": payload["name"],
        "district": payload["district"],
        "scenic_area": payload["scenic_area"],
        "lat": float(payload["lat"]),
        "lng": float(payload["lng"]),
        "slope": float(payload["slope"]),
        "lithology": payload["lithology"],
        "historical_landslide": int(payload["historical_landslide"]),
        "source": payload["source"],
        "reference_url": payload.get("reference_url") or None,
    }
    records.append(record)
    write_json(DISASTER_POINTS_FILE, records)
    return DisasterPoint(**record)


def add_shelter(payload: dict[str, Any]) -> Shelter:
    record = ShelterDB(
        id=f"shelter-{uuid4().hex[:10]}",
        name=payload["name"],
        area=payload["area"],
        lat=float(payload["lat"]),
        lng=float(payload["lng"]),
        capacity=int(payload["capacity"]),
        contact=payload["contact"],
        source=payload["source"],
    )
    with session_scope() as db:
        db.add(record)
        db.flush()
        db.refresh(record)
        return Shelter(
            id=record.id,
            name=record.name,
            area=record.area,
            lat=record.lat,
            lng=record.lng,
            capacity=record.capacity,
            contact=record.contact,
            source=record.source,
        )
