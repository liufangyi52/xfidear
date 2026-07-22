from fastapi import APIRouter, Depends

from backend.models import UserPublic
from backend.permissions import require_admin_role
from backend.services.auth_service import current_user
from backend.services.storage import list_broadcasts

router = APIRouter(prefix="/api/broadcasts", tags=["broadcasts"])


@router.get("")
def broadcasts(user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    return list_broadcasts()
