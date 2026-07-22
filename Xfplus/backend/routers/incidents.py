from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.models import IncidentAnalyzeRequest, IncidentCreate, IncidentStatusUpdate, LLMResponse, UserPublic
from backend.permissions import assert_scope_access, require_admin_role
from backend.services.auth_service import current_user
from backend.services.incident_service import (
    classify_incident,
    create_demo_incidents,
    create_incident,
    get_incident,
    incident_stats,
    list_incidents,
    nearest_shelter_for,
    update_incident_status,
)
from backend.services.llm_service import call_llm
from backend.services.message_service import create_system_message

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


@router.post("")
def submit_incident(payload: IncidentCreate, user: UserPublic = Depends(current_user)):
    if user.role == "resident" and user.district and payload.district and payload.district != user.district:
        raise HTTPException(status_code=403, detail="居民只能提交本人绑定区县内的事件")
    if user.role in {"county_admin", "community_admin"} and payload.district and payload.district != user.district:
        raise HTTPException(status_code=403, detail="事件区县超出当前权限范围")
    if user.role == "community_admin" and payload.community and user.community and payload.community != user.community:
        raise HTTPException(status_code=403, detail="事件社区超出当前权限范围")
    return create_incident(payload, user)


@router.get("")
def query_incidents(
    status: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    time_range: Optional[str] = Query(default=None),
    mine: bool = Query(default=False),
    user: UserPublic = Depends(current_user),
):
    incidents = list_incidents(
        user=user,
        status=status,
        incident_type=type,
        time_range=time_range,
        mine_only=mine,
    )
    return {"items": incidents, "stats": incident_stats(incidents)}


@router.put("/{incident_id}/status")
def set_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    user: UserPublic = Depends(current_user),
):
    require_admin_role(user)
    incident = get_incident(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    assert_scope_access(user, incident.get("district"), incident.get("community"))
    updated = update_incident_status(incident_id, payload.status)
    if updated and payload.status == "resolved":
        create_system_message(
            user,
            title="您上报的事件已完成处置",
            content=f"事件“{incident.get('description', '')[:40]}”已标记为已完成，请继续关注现场安全提示。",
            target_roles=[incident.get("reporter_role", "resident")],
            target_district=incident.get("district"),
            target_community=incident.get("community"),
            source_type="incident_resolved",
            related_id=incident_id,
        )
    return updated


@router.post("/demo")
def generate_demo_incidents(user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    incidents = create_demo_incidents(user)
    visible = list_incidents(user=user)
    return {"created": incidents, "items": visible, "stats": incident_stats(visible)}


@router.post("/analyze", response_model=LLMResponse)
def analyze_incident(payload: IncidentAnalyzeRequest, user: UserPublic = Depends(current_user)):
    incident = get_incident(payload.incident_id) if payload.incident_id else None
    if incident and user.role != "city_admin":
        if user.district and incident.get("district") and user.district != incident.get("district"):
            raise HTTPException(status_code=403, detail="事件超出当前权限范围")
        if user.role == "community_admin" and user.community and incident.get("community") not in {None, user.community}:
            raise HTTPException(status_code=403, detail="事件超出当前社区权限范围")
    description = payload.description or (incident or {}).get("description")
    if not description:
        raise HTTPException(status_code=400, detail="Provide incident_id or description")

    incident_type = payload.type or (incident or {}).get("type") or classify_incident(description)
    shelter = None
    if incident:
        shelter = incident.get("nearest_shelter") or nearest_shelter_for(incident["lat"], incident["lng"])

    prompt = f"""
你是张家界应急管理指挥助手，请对以下现场事件做 120 字以内研判，并给出 3 条处置建议。
事件类型：{incident_type}
事件描述：{description}
行政区域：{(incident or {}).get('district') or user.district or '张家界市'}
景区/地点：{(incident or {}).get('scenic_area') or '未明确'}
最近安置点：{shelter.get('name') if shelter else '待确认'}
输出格式：事件摘要、风险判断、建议行动。
"""
    result = call_llm(prompt)
    return LLMResponse(text=result["text"], fallback_used=result["fallback_used"], llm_provider=result["llm_provider"])
