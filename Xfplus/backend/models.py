from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["city_admin", "county_admin", "community_admin", "resident", "tourist"]
Priority = Literal["city", "county", "community", "normal"]
IncidentType = Literal["flood", "landslide", "road", "medical", "sos", "shelter", "other"]
IncidentStatus = Literal["pending", "responding", "resolved"]
IncidentSeverity = Literal["low", "medium", "high", "critical"]


class AudienceMessages(BaseModel):
    county_admin: str = ""
    resident: str = ""
    tourist: str = ""
    village_officer: str = ""
    scenic_manager: str = ""


class AlertBase(BaseModel):
    title: str
    disaster_type: str = "暴雨/山洪/滑坡"
    level: str = "橙色"
    affected_areas: List[str] = Field(default_factory=list)
    started_at: str = ""
    duration: str = ""
    advice: str = ""
    status: str = "active"
    data_source_note: str = "基于公开历史预警资料改编"
    audience_messages: AudienceMessages = Field(default_factory=AudienceMessages)
    district: Optional[str] = None
    community: Optional[str] = None


class AlertCreate(AlertBase):
    pass


class Alert(AlertBase):
    id: int
    created_at: str
    is_pushed: bool = False
    pushed_at: Optional[str] = None


class DisasterPoint(BaseModel):
    id: str
    name: str
    district: str
    scenic_area: str
    lat: float
    lng: float
    slope: float
    lithology: str
    historical_landslide: int
    source: str
    reference_url: Optional[str] = None


class Shelter(BaseModel):
    id: str
    name: str
    area: str
    lat: float
    lng: float
    capacity: int
    contact: str
    source: str


class BroadcastRecord(BaseModel):
    id: int
    alert_id: int = 0
    alert_title: str = ""
    audience: str = ""
    content: str = ""
    type: str = "管理端推送"
    source_type: str = "alert_push"
    play_count: int = 0
    created_at: str


class UserPublic(BaseModel):
    id: int
    username: str
    role: Role
    district: Optional[str] = None
    community: Optional[str] = None


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: Role
    district: Optional[str] = None
    community: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class AuthResponse(BaseModel):
    token: str
    user: UserPublic


class MessageCreate(BaseModel):
    title: str
    content: str
    target_roles: List[Role]
    target_district: Optional[str] = None
    target_community: Optional[str] = None
    target_user_id: Optional[int] = None
    source_type: str = "manual"
    related_id: Optional[int] = None
    parent_id: Optional[int] = None


class MessageAttachment(BaseModel):
    id: str
    name: str
    size: int
    content_type: str = "application/octet-stream"
    url: str = ""


class DispatchMessage(MessageCreate):
    id: int
    sender_id: int
    sender_role: Role
    priority: Priority
    status: str = "sent"
    reply_content: str = ""
    review_note: str = ""
    reviewed_by: Optional[int] = None
    reviewed_at: Optional[str] = None
    attachments: List[MessageAttachment] = Field(default_factory=list)
    created_at: str


class PublicSuggestionCreate(BaseModel):
    title: str
    content: str
    district: Optional[str] = None
    community: Optional[str] = None


class MessageReviewRequest(BaseModel):
    status: str = "replied"
    reply_content: str = ""
    review_note: str = ""


class MessageForwardRequest(BaseModel):
    title: str
    content: str
    target_roles: List[Role] = Field(default_factory=lambda: ["county_admin", "community_admin"])
    target_district: Optional[str] = None
    target_community: Optional[str] = None


class IncidentCreate(BaseModel):
    type: IncidentType = "other"
    description: str
    lat: float
    lng: float
    district: Optional[str] = None
    community: Optional[str] = None
    scenic_area: Optional[str] = None
    severity: IncidentSeverity = "medium"
    status: IncidentStatus = "pending"
    is_demo: bool = False
    source_title: str = ""
    source_org: str = ""
    source_url: str = ""
    source_date: str = ""
    workflow_steps: List[str] = Field(default_factory=list)


class Incident(IncidentCreate):
    id: int
    reporter_role: Role = "tourist"
    reporter_id: Optional[int] = None
    nearest_shelter: Optional[dict] = None
    need_review: bool = False
    created_at: str
    resolved_at: Optional[str] = None


class IncidentStatusUpdate(BaseModel):
    status: IncidentStatus


class IncidentAnalyzeRequest(BaseModel):
    incident_id: Optional[int] = None
    description: Optional[str] = None
    type: Optional[IncidentType] = None


class NotificationTestRequest(BaseModel):
    target: str = ""
    title: str
    content: str


class AskRequest(BaseModel):
    question: str
    context: Optional[str] = None


class AiChatRequest(BaseModel):
    question: str
    context_type: Optional[str] = None
    history: List[dict[str, Any]] = Field(default_factory=list)
    active_district: Optional[str] = None
    active_community: Optional[str] = None
    stream: bool = False


class LLMResponse(BaseModel):
    text: str
    fallback_used: bool
    llm_provider: str


class AiChatResponse(BaseModel):
    answer: str
    fallback_used: bool
    llm_provider: str


class AlertTextResponse(BaseModel):
    messages: AudienceMessages
    fallback_used: bool
    llm_provider: str


class PostmortemRequest(BaseModel):
    alert_id: int


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")
