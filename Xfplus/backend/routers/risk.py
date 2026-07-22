from fastapi import APIRouter

from backend.services.risk_engine import current_risk

router = APIRouter(prefix="/api/risk", tags=["risk"])


@router.get("/current")
def get_current_risk(district: str | None = None):
    return current_risk(district)
