from fastapi import HTTPException

from backend.models import UserPublic

ADMIN_ROLES = {"city_admin", "county_admin", "community_admin"}


def require_admin_role(user: UserPublic) -> None:
    if user.role not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="Only emergency management roles can access this operation")


def assert_scope_access(user: UserPublic, district: str | None = None, community: str | None = None) -> None:
    if user.role == "city_admin":
        return
    if user.role == "county_admin":
        if district and user.district != district:
            raise HTTPException(status_code=403, detail="Data is outside your district scope")
        return
    if user.role == "community_admin":
        if district and user.district != district:
            raise HTTPException(status_code=403, detail="Data is outside your district scope")
        if community and user.community and community != user.community:
            raise HTTPException(status_code=403, detail="Data is outside your community scope")
        return
    raise HTTPException(status_code=403, detail="No management permission")


def in_user_scope(user: UserPublic, district: str | None = None, community: str | None = None) -> bool:
    if user.role == "city_admin":
        return True
    if user.role in {"county_admin", "community_admin", "resident", "tourist"}:
        if user.district and district and user.district != district:
            return False
        if user.role == "community_admin" and user.community and community and user.community != community:
            return False
    return True
