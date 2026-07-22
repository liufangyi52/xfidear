import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from backend.models import (
    AiChatRequest,
    AiChatResponse,
    AlertBase,
    AlertTextResponse,
    AudienceMessages,
    AskRequest,
    LLMResponse,
    MessageCreate,
    PostmortemRequest,
    UserPublic,
    now_iso,
)
from backend.permissions import assert_scope_access, require_admin_role
from backend.routers.alerts import _broadcast_content, _push_audience_messages
from backend.services.alert_text_generator import generate_multi_role_texts
from backend.services.auth_service import current_user
from backend.services.disaster_points import load_disaster_points, load_shelters
from backend.services.incident_service import (
    create_demo_incidents,
    get_incident,
    incident_stats,
    list_incidents,
    update_incident_status,
)
from backend.services.llm_service import call_llm
from backend.services.message_service import create_message, create_system_message
from backend.services.risk_engine import current_risk
from backend.services.storage import add_broadcast, get_alert, list_alerts, list_broadcasts, update_alert

router = APIRouter(prefix="/api", tags=["ai"])

DEMO_COUNTY_DISTRICTS = {"永定区", "武陵源区", "桑植县", "慈利县"}


def _clean_scope_value(value: str | None) -> str | None:
    cleaned = (value or "").strip()
    return cleaned or None


def _effective_scope(user: UserPublic, payload: AiChatRequest) -> tuple[str | None, str | None]:
    active_district = _clean_scope_value(payload.active_district)
    active_community = _clean_scope_value(payload.active_community)

    if user.role == "city_admin":
        if active_district and active_district not in DEMO_COUNTY_DISTRICTS:
            raise HTTPException(status_code=403, detail="Requested district is outside the city scope")
        return active_district, active_community

    if user.role == "county_admin":
        district = active_district or user.district
        if active_district and active_district not in DEMO_COUNTY_DISTRICTS and active_district != user.district:
            raise HTTPException(status_code=403, detail="Requested district is outside your allowed demo scope")
        return district, None

    if user.role == "community_admin":
        district = active_district or user.district
        community = active_community or user.community
        if active_district and active_district not in DEMO_COUNTY_DISTRICTS and active_district != user.district:
            raise HTTPException(status_code=403, detail="Requested district is outside your allowed demo scope")
        return district, community

    return user.district, user.community


def _scope_note(user: UserPublic) -> str:
    if user.role == "city_admin":
        return "全市"
    if user.role == "county_admin":
        return user.district or "本区县"
    if user.role == "community_admin":
        return f"{user.district or ''}{user.community or '本社区'}"
    if user.role == "resident":
        return user.district or "居民所在区县"
    return "游客当前可见的公开数据"


def _aggregated_context(user: UserPublic, payload: AiChatRequest) -> str:
    district, community = _effective_scope(user, payload)
    alerts = list_alerts(limit=5, district=district)
    if user.role != "city_admin" and district:
        alerts = [item for item in alerts if item.get("district") == district]
    if user.role == "community_admin" and community:
        alerts = [item for item in alerts if not item.get("community") or item.get("community") == community]
    scope_user = user.model_copy(update={"district": district, "community": community})
    incidents = list_incidents(user=scope_user)
    if district:
        incidents = [item for item in incidents if item.get("district") == district]
    if community and user.role == "community_admin":
        incidents = [item for item in incidents if not item.get("community") or item.get("community") == community]
    stats = incident_stats(incidents)
    disaster_points = [
        point.model_dump()
        for point in load_disaster_points()
        if not district or point.district == district
    ][:8]
    shelters = [
        shelter.model_dump()
        for shelter in load_shelters()
        if not district or shelter.area == district or district in shelter.area
    ][:8]
    broadcasts = list_broadcasts()[:5] if user.role == "city_admin" and not district else []
    context = {
        "user": {
            "role": user.role,
            "scope": community or district or _scope_note(user),
            "district": district,
            "community": community,
        },
        "active_scope": {
            "district": district,
            "community": community,
            "source": "login_selection" if payload.active_district or payload.active_community else "user_profile",
        },
        "permission_boundary": {
            "visible_level": user.role,
            "district_locked": user.role in {"county_admin", "community_admin", "resident"} and bool(district),
            "community_locked": user.role == "community_admin" and bool(community),
            "rule": "Answer only from active_scope data. Do not cite city-level, other-district, or other-community management information unless the user role is city_admin.",
        },
        "incident_stats": stats,
        "latest_alerts": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "level": item.get("level"),
                "status": item.get("status"),
                "district": item.get("district"),
                "is_pushed": item.get("is_pushed"),
                "advice": item.get("advice"),
            }
            for item in alerts
        ],
        "latest_incidents": [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "severity": item.get("severity"),
                "status": item.get("status"),
                "district": item.get("district"),
                "community": item.get("community"),
                "scenic_area": item.get("scenic_area"),
                "description": item.get("description"),
                "nearest_shelter": item.get("nearest_shelter"),
                "created_at": item.get("created_at"),
            }
            for item in incidents[:8]
        ],
        "risk_points": [
            {
                "name": item.get("name"),
                "district": item.get("district"),
                "scenic_area": item.get("scenic_area"),
                "slope": item.get("slope"),
                "lat": item.get("lat"),
                "lng": item.get("lng"),
            }
            for item in disaster_points
        ],
        "shelters": [
            {
                "name": item.get("name"),
                "area": item.get("area"),
                "capacity": item.get("capacity"),
                "contact": item.get("contact"),
                "lat": item.get("lat"),
                "lng": item.get("lng"),
            }
            for item in shelters
        ],
        "recent_broadcasts": [
            {
                "alert_title": item.get("alert_title"),
                "audience": item.get("audience"),
                "content": item.get("content"),
                "created_at": item.get("created_at"),
            }
            for item in broadcasts
        ],
    }
    return json.dumps(context, ensure_ascii=False, indent=2)


def _alert_generation_context(user: UserPublic, alert: AlertBase) -> str:
    district = alert.district or user.district
    community = alert.community or user.community
    if user.role == "city_admin":
        district = alert.district
        community = alert.community
    elif user.role == "county_admin":
        district = district or user.district
        community = None
    elif user.role == "community_admin":
        district = district or user.district
        community = community or user.community

    assert_scope_access(user, district, community)
    scope_user = user.model_copy(update={"district": district, "community": community})
    risk = current_risk(district if district else None)
    incidents = list_incidents(user=scope_user, time_range="24h")
    if district:
        incidents = [item for item in incidents if item.get("district") == district]
    if user.role == "community_admin" and community:
        incidents = [item for item in incidents if not item.get("community") or item.get("community") == community]
    alerts = list_alerts(limit=5, district=district)
    shelters = [
        shelter.model_dump()
        for shelter in load_shelters()
        if not district or shelter.area == district or district in shelter.area
    ][:8]
    context = {
        "user_scope": {
            "role": user.role,
            "district": district,
            "community": community,
        },
        "weather": risk.get("weather", {}),
        "risk_points": [
            {
                "name": item.get("name"),
                "district": item.get("district"),
                "scenic_area": item.get("scenic_area"),
                "risk_level": item.get("risk_level"),
                "risk_score": item.get("risk_score"),
                "action": item.get("action"),
                "nearby_shelter": item.get("nearby_shelter"),
            }
            for item in risk.get("points", [])[:5]
        ],
        "latest_incidents_24h": [
            {
                "id": item.get("id"),
                "type": item.get("type"),
                "severity": item.get("severity"),
                "status": item.get("status"),
                "district": item.get("district"),
                "community": item.get("community"),
                "scenic_area": item.get("scenic_area"),
                "description": item.get("description"),
                "nearest_shelter": item.get("nearest_shelter"),
                "created_at": item.get("created_at"),
            }
            for item in incidents[:5]
        ],
        "incident_stats_24h": incident_stats(incidents),
        "shelters": [
            {
                "name": item.get("name"),
                "area": item.get("area"),
                "capacity": item.get("capacity"),
                "contact": item.get("contact"),
            }
            for item in shelters[:5]
        ],
        "recent_alerts": [
            {
                "id": item.get("id"),
                "title": item.get("title"),
                "level": item.get("level"),
                "status": item.get("status"),
                "district": item.get("district"),
                "is_pushed": item.get("is_pushed"),
                "advice": item.get("advice"),
            }
            for item in alerts
        ],
    }
    return json.dumps(context, ensure_ascii=False, indent=2)


def _status_from_text(text: str) -> str | None:
    if any(word in text for word in ["已完成", "完成", "解决", "resolved"]):
        return "resolved"
    if any(word in text for word in ["处理中", "处置中", "响应", "responding"]):
        return "responding"
    if any(word in text for word in ["待核实", "待处理", "pending"]):
        return "pending"
    return None


def _target_roles_from_text(text: str) -> list[str]:
    roles = []
    if "区县" in text:
        roles.append("county_admin")
    if "社区" in text or "村" in text:
        roles.append("community_admin")
    if "居民" in text:
        roles.append("resident")
    if "游客" in text:
        roles.append("tourist")
    return roles or ["resident", "tourist"]


def _number_after_keyword(text: str, keywords: list[str]) -> int | None:
    for keyword in keywords:
        match = re.search(rf"{keyword}\s*#?(\d+)", text, re.IGNORECASE)
        if match:
            return int(match.group(1))
    match = re.search(r"#(\d+)", text)
    return int(match.group(1)) if match else None


def _extract_message_content(text: str) -> str | None:
    for marker in ["内容：", "内容:", "发送：", "发送:", "通知：", "通知:"]:
        if marker in text:
            return text.split(marker, 1)[1].strip()
    return None


def _try_run_command(question: str, user: UserPublic) -> str | None:
    text = question.strip()
    if not text:
        return None
    if any(word in text for word in ["如何", "怎么", "怎样", "什么是", "能否", "可以吗", "说明", "介绍"]):
        return None

    if any(word in text for word in ["生成演示事件", "创建演示事件", "模拟事件"]):
        require_admin_role(user)
        created = create_demo_incidents(user)
        return f"已创建 {len(created)} 条演示事件，并按你的权限范围进入事件管理。"

    if "事件" in text and any(word in text for word in ["标记", "改为", "设为", "更新"]):
        require_admin_role(user)
        incident_id = _number_after_keyword(text, ["事件", "incident"])
        status = _status_from_text(text)
        if not incident_id or not status:
            return "我可以更新事件状态，请说明事件编号和目标状态，例如：把事件 3 标记为处理中。"
        incident = get_incident(incident_id)
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        assert_scope_access(user, incident.get("district"), incident.get("community"))
        updated = update_incident_status(incident_id, status)
        if updated and status == "resolved":
            create_system_message(
                user,
                title="您上报的事件已完成处置",
                content=f"事件“{incident.get('description', '')[:40]}”已标记为已完成，请继续关注现场安全提示。",
                target_roles=[incident.get("reporter_role", "resident")],
                target_district=incident.get("district"),
                target_community=incident.get("community"),
                source_type="assistant_incident_resolved",
                related_id=incident_id,
            )
        labels = {"pending": "待核实", "responding": "处置中", "resolved": "已完成"}
        return f"已将事件 {incident_id} 更新为“{labels[status]}”。"

    if "预警" in text and any(word in text for word in ["推送", "发布"]):
        require_admin_role(user)
        alert_id = _number_after_keyword(text, ["预警", "alert"])
        if not alert_id:
            return "我可以推送预警，请说明预警编号，例如：推送预警 2。"
        alert = get_alert(alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Alert not found")
        assert_scope_access(user, alert.get("district"), alert.get("community"))
        pushed_at = now_iso()
        updated = update_alert(alert_id, {"is_pushed": True, "pushed_at": pushed_at})
        if user.role == "city_admin":
            audience = "区县级应急管理人员"
        else:
            audience = "本区县居民与游客"
        add_broadcast(
            updated,
            audience,
            _broadcast_content(updated),
            "AI助手推送",
            source_type="assistant_alert_push",
            created_at=pushed_at,
        )
        messages = _push_audience_messages(updated, user, "assistant_alert_push")
        return f"已推送预警 {alert_id}：{alert.get('title')}，精准触达 {len(messages)} 个账号。"

    if any(word in text for word in ["发送消息", "下发消息", "通知"]) and _extract_message_content(text):
        require_admin_role(user)
        content = _extract_message_content(text) or ""
        roles = _target_roles_from_text(text)
        message = create_message(
            user,
            MessageCreate(
                title="AI助手下发通知",
                content=content,
                target_roles=roles,
                target_district=None if user.role == "city_admin" else user.district,
                target_community=user.community if user.role == "community_admin" else None,
                source_type="assistant_command",
            ),
        )
        return f"已发送消息 #{message.id}，目标角色：{', '.join(roles)}。"

    return None


def _safe_history(payload: AiChatRequest, user: UserPublic) -> list[dict]:
    blocked_terms = {
        "city_admin",
        "市级应急管理",
        "张家界市级",
        "全市指挥",
    }
    safe_items = []
    for item in payload.history[-5:]:
        role = str(item.get("role", "user"))
        content = str(item.get("content", ""))[:800]
        if user.role != "city_admin" and any(term in content for term in blocked_terms):
            continue
        safe_items.append({"role": role, "content": content})
    return safe_items


def _safe_scoped_history(
    payload: AiChatRequest,
    user: UserPublic,
    district: str | None = None,
    community: str | None = None,
) -> list[dict]:
    blocked_terms = {
        "city_admin",
        "市级",
        "全市",
        "市级应急管理",
        "张家界市级",
        "全市指挥",
    }
    peer_districts = DEMO_COUNTY_DISTRICTS - ({district} if district else set())
    safe_items = []
    for item in payload.history[-5:]:
        role = str(item.get("role", "user"))
        content = str(item.get("content", ""))[:800]
        if user.role != "city_admin" and any(term in content for term in blocked_terms):
            continue
        if user.role != "city_admin" and any(peer in content for peer in peer_districts):
            continue
        if (
            user.role == "community_admin"
            and community
            and community not in content
            and any(word in content for word in ["社区", "村", "居委会"])
        ):
            continue
        safe_items.append({"role": role, "content": content})
    return safe_items


@router.post("/ai/chat", response_model=AiChatResponse)
def ai_chat(payload: AiChatRequest, user: UserPublic = Depends(current_user)):
    command_result = _try_run_command(payload.question, user)
    if command_result:
        return AiChatResponse(answer=command_result, fallback_used=False, llm_provider="system-action")

    district, community = _effective_scope(user, payload)
    context = _aggregated_context(user, payload)
    history_text = "\n".join(
        f"{item['role']}: {item['content']}" for item in _safe_scoped_history(payload, user, district, community)
    )
    boundary_text = (
        f"权限边界：当前用户角色是 {user.role}，当前工作台区县是 {district or '全市'}，"
        f"当前社区是 {community or '无'}。如果不是 city_admin，只能回答当前工作台区县/社区的数据，"
        "不要引用市级管理人员资料、其他区县资料、其他社区资料或历史对话里的越界内容；"
        "数据不足时直接说明当前范围内没有数据。"
    )
    prompt = f"""
你是“张家界·智瞳应急平台”的全局 AI 助手，可以提供应急决策辅助、公众避险建议、灾害知识讲解和系统操作指引。
请严格基于下面 JSON 中的当前系统数据回答；如果系统数据不足，请明确说“当前系统数据未提供”，再给出可执行的下一步建议。
不要把不同问题回答成同一套模板。回答要结合用户角色、权限范围、最新预警、事件、风险点和安置点。
如果用户要求执行操作但你没有实际执行权限或缺少编号/内容，请说明需要补充什么，不要假装已操作。

当前系统数据：
{context}

对话历史：
{history_text or '无'}

问题类型：{payload.context_type or '通用'}
用户问题：{payload.question}
"""
    prompt = f"{boundary_text}\n{prompt}"
    result = call_llm(prompt)
    return AiChatResponse(
        answer=result["text"],
        fallback_used=result["fallback_used"],
        llm_provider=result["llm_provider"],
    )


@router.post("/ask", response_model=LLMResponse)
def ask(payload: AskRequest, user: UserPublic = Depends(current_user)):
    result = ai_chat(AiChatRequest(question=payload.question, context_type="legacy"), user)
    return LLMResponse(text=result.answer, fallback_used=result.fallback_used, llm_provider=result.llm_provider)


@router.post("/generate_alert_text", response_model=AlertTextResponse)
def generate_alert_text(alert: AlertBase, user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    context = _alert_generation_context(user, alert)
    result = generate_multi_role_texts(alert, context)
    result["messages"] = _filter_alert_messages_for_sender(result["messages"], user)
    return AlertTextResponse(
        messages=result["messages"],
        fallback_used=result["fallback_used"],
        llm_provider=result["llm_provider"],
    )


def _filter_alert_messages_for_sender(messages: AudienceMessages, user: UserPublic) -> AudienceMessages:
    data = messages.model_dump()
    if user.role == "city_admin":
        return AudienceMessages(county_admin=data.get("county_admin", ""))
    if user.role == "county_admin":
        return AudienceMessages(
            resident=data.get("resident", ""),
            tourist=data.get("tourist", ""),
        )
    return messages


@router.post("/generate_postmortem", response_model=LLMResponse)
def generate_postmortem(payload: PostmortemRequest, user: UserPublic = Depends(current_user)):
    require_admin_role(user)
    alert = get_alert(payload.alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    related = [item for item in list_broadcasts() if item["alert_id"] == payload.alert_id]
    prompt = (
        "请仅判断本次预警复盘的风险侧重点，返回一句不超过40字的专业研判，"
        "不要寒暄、不要标题、不要Markdown。"
        f"事件：{alert}\n播报记录：{related}"
    )
    result = call_llm(prompt)
    report = _build_postmortem_report(alert, related, _clean_postmortem_text(result["text"], alert.get("title", "")))
    return LLMResponse(
        text=report,
        fallback_used=result["fallback_used"],
        llm_provider=result["llm_provider"],
    )


def _build_postmortem_report(alert: dict, broadcasts: list[dict], ai_focus: str = "") -> str:
    title = str(alert.get("title") or "预警事件")
    alert_id = alert.get("id", "")
    level = str(alert.get("level") or "未标明")
    created_at = _format_datetime(alert.get("created_at"))
    pushed_at = _format_datetime(alert.get("pushed_at")) if alert.get("pushed_at") else "未推送"
    review_date = _format_date(alert.get("pushed_at") or alert.get("created_at"))
    response_seconds = _seconds_between(alert.get("created_at"), alert.get("pushed_at"))
    response_text = _response_text(response_seconds, bool(alert.get("is_pushed")))
    areas = "、".join(str(item) for item in alert.get("affected_areas") or [] if str(item).strip()) or "未标明"
    duration = str(alert.get("duration") or "未标明")
    advice = str(alert.get("advice") or "未填写")
    messages = alert.get("audience_messages") or {}
    filled_roles = _filled_audience_roles(messages)
    broadcast_count = len(broadcasts)
    latest_broadcast = _format_datetime(broadcasts[0].get("created_at")) if broadcasts else "暂无广播记录"
    push_types = "、".join(sorted({str(item.get("type") or "管理端推送") for item in broadcasts})) if broadcasts else "暂无"
    audience_names = "、".join(sorted({str(item.get("audience") or "预警推送对象") for item in broadcasts})) if broadcasts else "暂无"
    focus_sentence = _postmortem_focus(ai_focus, areas)

    return "\n".join(
        [
            "张家界·智瞳应急平台预警事件复盘报告",
            f"事件名称：{title}",
            f"事件ID：{alert_id}",
            f"预警等级：{level}",
            f"复盘时间：{review_date}",
            "一、响应时效评估",
            f"    预警创建时间：{created_at}",
            f"    预警推送时间：{pushed_at}",
            f"    响应时效：{response_text}",
            "二、文案质量评估",
            f"    结构清晰：文案围绕“预警概要—处置要求—分角色通知”组织，覆盖预警等级、影响区域、持续时间和处置要求，便于管理端快速抓取核心信息。",
            f"    内容完整：本次预警影响区域为{areas}，持续时间为{duration}，处置要求为“{advice}”，关键要素完整。",
            f"    角色化精准：已形成{filled_roles}等差异化通知，能够区分管理人员、居民、游客和现场协同人员的行动重点。",
            f"    数据支撑：文案结合系统事件、广播推送记录和分角色通知内容形成复盘依据。{focus_sentence}",
            "三、触达情况分析",
            f"    推送状态：{'已推送' if alert.get('is_pushed') else '未推送'}。",
            f"    推送记录：系统记录到{broadcast_count}条广播/推送记录，最近一次记录时间为{latest_broadcast}。",
            f"    推送对象：记录显示推送对象包括{audience_names}，推送类型包括{push_types}。",
            "    触达效果缺失：当前系统已记录推送动作和广播内容，但尚未形成按角色、区县、渠道统计的送达率、阅读率、点击率和确认反馈数据，因此无法量化最终阅读效果。",
            "四、不足之处",
            "    1. 触达效果无法量化：系统缺少推送后的送达、阅读、点击和确认反馈统计，无法判断预警信息是否真正被目标人员接收并阅读。",
            "    2. 闭环反馈不完整：缺少区县管理人员、景区管理者、村干部等关键责任人的接收确认、执行进度和处置结果反馈。",
            "    3. 渠道效能缺少对比：广播、站内消息、APP、短信、微信等渠道尚未形成统一效果对比，不利于后续选择最高效触达渠道。",
            "五、改进建议",
            "    1. 建立触达统计看板：在系统后台增加送达率、阅读率、点击率、确认率等指标，并支持按区县、角色和渠道下钻分析。",
            "    2. 增加反馈确认机制：要求关键责任人在收到预警后完成“一键确认”或“执行反馈”，系统自动记录确认时间和反馈内容。",
            "    3. 完善渠道记录：明确记录预警通过哪些渠道触达，便于评估广播、站内消息、短信、APP等不同渠道的实际效果。",
            "    4. 强化时间校验：对预警创建时间、推送时间和持续时间进行逻辑校验，避免复盘中出现时间口径不一致。",
            f"六、总结：本次{level}预警在响应速度和文案完整性方面表现较好，能够围绕{areas}形成较清晰的处置通知。但触达量化、接收确认和执行反馈仍存在短板，建议优先补齐推送统计和闭环反馈能力，提升智瞳应急平台的实战复盘价值。",
        ]
    )


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    for pattern in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, pattern)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _format_datetime(value: object) -> str:
    parsed = _parse_datetime(value)
    return parsed.strftime("%Y-%m-%d %H:%M:%S") if parsed else str(value or "未记录")


def _format_date(value: object) -> str:
    parsed = _parse_datetime(value)
    return parsed.strftime("%Y-%m-%d") if parsed else str(value or "未记录")[:10]


def _seconds_between(start: object, end: object) -> int | None:
    started = _parse_datetime(start)
    ended = _parse_datetime(end)
    if not started or not ended:
        return None
    return max(0, int((ended - started).total_seconds()))


def _response_text(seconds: int | None, is_pushed: bool) -> str:
    if not is_pushed:
        return "未完成推送，无法形成完整响应时效评价。"
    if seconds is None:
        return "已完成推送，但创建时间或推送时间缺失，无法精确计算耗时。"
    if seconds < 60:
        return f"优秀。从预警生成到完成推送仅用时 {seconds} 秒，实现了秒级响应，能够为下游应急行动争取宝贵时间。"
    minutes = seconds // 60
    remain = seconds % 60
    remain_text = f"{minutes} 分 {remain} 秒" if remain else f"{minutes} 分钟"
    if seconds <= 300:
        return f"良好。从预警生成到完成推送用时 {remain_text}，能够满足快速响应要求。"
    return f"需优化。从预警生成到完成推送用时 {remain_text}，建议压缩审核与推送链路。"


def _filled_audience_roles(messages: dict) -> str:
    labels = {
        "county_admin": "区县管理人员",
        "resident": "居民",
        "tourist": "游客",
        "village_officer": "村干部",
        "scenic_manager": "景区管理者",
    }
    names = [label for key, label in labels.items() if str(messages.get(key) or "").strip()]
    return "、".join(names) if names else "相关对象"


def _postmortem_focus(ai_focus: str, areas: str) -> str:
    focus = re.sub(r"^复盘摘要[:：]", "", str(ai_focus or "")).strip()
    if not focus or len(focus) > 80 or "改进建议" in focus or "怎么" in focus:
        return f"本次复盘重点关注{areas}的预警响应、分角色通知和推送闭环。"
    return focus.rstrip("。") + "。"


def _clean_postmortem_text(text: str, alert_title: str = "") -> str:
    title_candidates = {
        alert_title,
        f"{alert_title}复盘报告",
        f"{alert_title}复盘报告。",
        f"【{alert_title}】复盘报告",
        f"《{alert_title}》复盘报告",
    }
    lines = []
    for raw_line in str(text or "").replace("\r", "").split("\n"):
        line = re.sub(r"^[\s#>*-]+", "", raw_line)
        line = line.replace("*", "")
        line = re.sub(r"#{1,6}", "", line).strip()
        if not line:
            continue
        if line in title_candidates:
            continue
        if re.match(r"^好的[，,]", line):
            continue
        if re.match(r"^根据.*生成.*复盘报告[。.]?$", line):
            continue
        if re.match(r"^现为您.*复盘报告[。.]?$", line):
            continue
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
