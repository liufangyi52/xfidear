import json
import re
from typing import Dict

from backend.models import AlertBase, AudienceMessages
from backend.services.alert_message_builder import to_audience_messages
from backend.services.llm_service import call_llm


def _parse_json_object(text: str) -> dict:
    cleaned = (text or "").strip()
    if not cleaned:
        return {}
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", cleaned)
    if not match:
        return {}
    try:
        return json.loads(match.group(0))
    except Exception:
        return {}


def generate_multi_role_texts(alert: AlertBase, system_context: str = "") -> Dict[str, object]:
    prompt = (
        "你是张家界应急管理助手。请根据以下预警事件生成五段中文通知，"
        "分别面向区县管理人员、居民、游客、村干部、景区管理者。输出严格 JSON，键名为 "
        "county_admin,resident,tourist,village_officer,scenic_manager。\n"
        "只输出 JSON 对象，不要输出 Markdown 代码块、解释文字或列表前缀。\n"
        "必须结合系统实时数据，包括当前雨情、风险点、现场事件、安置点位置、估算承载和既有预警。"
        "如果系统实时数据不足，请不要编造具体数值，只根据已提供字段给出可执行方案。\n"
        f"系统实时数据：{system_context or '当前系统数据未提供'}\n"
        f"事件：{alert.title}\n"
        f"等级：{alert.level}\n"
        f"影响区域：{','.join(alert.affected_areas)}\n"
        f"持续时间：{alert.duration}\n"
        f"建议：{alert.advice}\n"
        "每段文案要包含：风险判断、目标人群行动、集合/安置或避险位置、注意事项。"
    )
    result = call_llm(prompt)
    parsed = _parse_json_object(result["text"])
    messages = AudienceMessages(
        county_admin=parsed.get("county_admin", "请区县管理人员会商研判雨情、风险点、安置点开放状态和交通管控，组织属地巡查处置。"),
        resident=parsed.get("resident", "请居民关注雨情，远离溪沟和陡坡，必要时转移至安全区域。"),
        tourist=parsed.get("tourist", "请游客停止高风险游览，前往游客中心或最近安置点。"),
        village_officer=parsed.get("village_officer", "请村干部巡查隐患点，组织重点人群做好转移准备。"),
        scenic_manager=parsed.get("scenic_manager", "请景区管理方加强广播巡查，暂停高风险游线。"),
    )
    messages = to_audience_messages({**alert.model_dump(), "audience_messages": messages})
    return {**result, "messages": messages}
