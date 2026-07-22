from typing import Any, Mapping

from backend.models import AudienceMessages

ROLE_KEYS = ("county_admin", "resident", "tourist", "village_officer", "scenic_manager")


def ensure_distinct_audience_messages(alert: Mapping[str, Any]) -> dict[str, str]:
    messages = _as_dict(alert.get("audience_messages"))
    base = _alert_context(alert)
    generated = {
        "county_admin": (
            f"区县管理方案：{base['level']}预警已覆盖{base['areas']}，请区县应急、自然资源、文旅、交通等部门立即会商，"
            f"核查雨情、隐患点、景区客流和安置点开放状态，向乡镇街道下达巡查、管控、转移和信息报送任务。{base['advice']}"
        ),
        "resident": (
            f"居民方案：{base['level']}预警期间，{base['areas']}居民请关注雨情和转移通知，"
            f"远离溪沟、陡坡、切坡建房和低洼积水区域。老人、儿童、行动不便人员优先向村部、社区避险点或最近安置点转移，"
            f"不要自行前往涉水路段查看险情。{base['advice']}"
        ),
        "tourist": (
            f"游客方案：{base['duration']}内暂停峡谷涉水、临崖步道、玻璃桥入口道路等高风险游览，"
            f"听从景区工作人员引导，向游客服务中心、室内候客区或最近安置点有序转移。"
            f"请保留随身证件和通讯电量，不要脱离团队或逆行返回景点。{base['advice']}"
        ),
        "village_officer": (
            f"村干部方案：立即按{base['areas']}风险范围组织巡查，重点核查溪沟两侧、临坡住户、独居老人和游客滞留点。"
            f"建立转移名单和到达确认，安排人员在路口、桥涵、易滑坡点值守，必要时联系乡镇、社区和安置点联动处置。{base['advice']}"
        ),
        "scenic_manager": (
            f"景区管理者方案：立即暂停涉水游线、临崖步道和受影响入口道路，关闭风险点位并设置硬隔离。"
            f"通过广播、电子屏、工作人员分段引导游客向游客服务中心或安全集结区转移，同步准备交通接驳、医疗救助和人数清点。{base['advice']}"
        ),
    }

    normalized: dict[str, str] = {}
    seen: set[str] = set()
    advice = _clean(alert.get("advice"))
    for key in ROLE_KEYS:
        current = _clean(messages.get(key))
        if not current or current == advice or current in seen:
            current = generated[key]
        normalized[key] = current
        seen.add(current)
    return normalized


def to_audience_messages(alert: Mapping[str, Any]) -> AudienceMessages:
    return AudienceMessages(**ensure_distinct_audience_messages(alert))


def _as_dict(value: Any) -> dict[str, str]:
    if isinstance(value, AudienceMessages):
        return value.model_dump()
    if isinstance(value, Mapping):
        return {key: _clean(value.get(key)) for key in ROLE_KEYS}
    return {}


def _alert_context(alert: Mapping[str, Any]) -> dict[str, str]:
    areas_value = alert.get("affected_areas") or []
    if isinstance(areas_value, str):
        areas = areas_value
    else:
        areas = "、".join(str(item) for item in areas_value if str(item).strip())
    return {
        "level": _clean(alert.get("level")) or "当前",
        "areas": areas or "受影响区域",
        "duration": _clean(alert.get("duration")) or "预警时段",
        "advice": _clean(alert.get("advice")) or "请按现场指引及时避险。",
    }


def _clean(value: Any) -> str:
    return str(value or "").strip()
