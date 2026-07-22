import json
from typing import Any, Dict

import requests
import websocket

from backend.config import get_settings


def call_llm(prompt: str, use_fallback: bool = True) -> Dict[str, Any]:
    settings = get_settings()

    if settings.deepseek_api_key:
        try:
            return _call_deepseek(
                prompt,
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                model=settings.deepseek_model,
                timeout=settings.ai_timeout_seconds,
            )
        except Exception:
            if not use_fallback:
                raise

    if settings.iflytek_appid and settings.iflytek_api_key and settings.iflytek_api_secret:
        try:
            return _call_spark_ws(
                prompt,
                appid=settings.iflytek_appid,
                api_key=settings.iflytek_api_key,
                api_secret=settings.iflytek_api_secret,
                model=settings.iflytek_model,
                timeout=settings.ai_timeout_seconds,
            )
        except Exception:
            if not use_fallback:
                raise

    if use_fallback and settings.fallback_llm_type.lower() == "qwen" and settings.dashscope_api_key:
        try:
            return _call_qwen(prompt, settings.dashscope_api_key, settings.ai_timeout_seconds)
        except Exception:
            pass

    return {"text": _mock_answer(prompt), "fallback_used": True, "llm_provider": "mock"}


def _call_deepseek(prompt: str, api_key: str, base_url: str, model: str, timeout: int) -> Dict[str, Any]:
    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model or "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是张家界智瞳应急平台。必须基于用户可见的系统数据回答，"
                        "没有数据支撑时要明确说明。回答要简洁、可执行，避免编造。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.35,
            "max_tokens": 1200,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or []
    text = ""
    if choices:
        text = choices[0].get("message", {}).get("content", "") or choices[0].get("text", "")
    return {"text": text.strip(), "fallback_used": False, "llm_provider": "deepseek"}


def _spark_domain(model: str) -> tuple[str, str, str]:
    mapping = {
        "spark-lite": ("spark-api.xf-yun.com", "/v1.1/chat", "general"),
        "general": ("spark-api.xf-yun.com", "/v1.1/chat", "general"),
        "generalv3": ("spark-api.xf-yun.com", "/v3.1/chat", "generalv3"),
        "generalv3.5": ("spark-api.xf-yun.com", "/v3.5/chat", "generalv3.5"),
    }
    return mapping.get(model or "generalv3", mapping["generalv3"])


def _call_spark_ws(prompt: str, appid: str, api_key: str, api_secret: str, model: str, timeout: int) -> Dict[str, Any]:
    # 讯飞星火 WebSocket 鉴权调用。密钥只从环境变量读取，禁止写入代码或文档。
    import base64
    import hashlib
    import hmac
    from datetime import datetime
    from time import mktime
    from urllib.parse import urlencode
    from wsgiref.handlers import format_date_time

    host, path, domain = _spark_domain(model)
    date = format_date_time(mktime(datetime.utcnow().timetuple()))
    signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
    signature_sha = hmac.new(api_secret.encode("utf-8"), signature_origin.encode("utf-8"), digestmod=hashlib.sha256).digest()
    signature = base64.b64encode(signature_sha).decode("utf-8")
    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode("utf-8")).decode("utf-8")
    ws = websocket.create_connection(
        f"wss://{host}{path}?{urlencode({'authorization': authorization, 'date': date, 'host': host})}",
        timeout=timeout,
    )
    payload = {
        "header": {"app_id": appid, "uid": "zjj-smart-eye-v1"},
        "parameter": {"chat": {"domain": domain, "temperature": 0.4, "max_tokens": 2048}},
        "payload": {"message": {"text": [{"role": "user", "content": prompt}]}},
    }
    ws.send(json.dumps(payload, ensure_ascii=False))
    chunks = []
    try:
        while True:
            data = json.loads(ws.recv())
            header = data.get("header", {})
            if header.get("code", 0) != 0:
                raise RuntimeError(header.get("message", "Spark API returned an error"))
            choices = data.get("payload", {}).get("choices", {})
            for item in choices.get("text", []):
                chunks.append(item.get("content", ""))
            if choices.get("status") == 2:
                break
    finally:
        ws.close()
    return {"text": "".join(chunks), "fallback_used": False, "llm_provider": "spark"}


def _call_qwen(prompt: str, api_key: str, timeout: int) -> Dict[str, Any]:
    response = requests.post(
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "qwen-turbo",
            "input": {"messages": [{"role": "user", "content": prompt}]},
            "parameters": {"temperature": 0.4},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return {
        "text": data.get("output", {}).get("text", ""),
        "fallback_used": True,
        "llm_provider": "qwen",
    }


def _mock_answer(prompt: str) -> str:
    if "resident,tourist" in prompt or "county_admin,resident" in prompt:
        return json.dumps(
            {
                "county_admin": "请区县应急管理人员立即会商雨情、隐患点、客流、安置点开放状态和估算承载，向乡镇街道下达巡查、管控、转移和信息报送任务。",
                "resident": "请低洼地带和临坡住户关注雨情，提前转移老人儿童，避免靠近溪沟和切坡建房区域。",
                "tourist": "请游客暂停金鞭溪、峡谷、临崖步道等高风险游览，前往最近游客中心或安置点等待通知。",
                "village_officer": "请村干部立即巡查隐患点、溪沟两侧和独居老人住户，必要时启动转移避险台账。",
                "scenic_manager": "请景区管理方暂停涉水和临崖游线，加强广播巡查，联动交通、医疗和安置点资源。",
            },
            ensure_ascii=False,
        )
    if "复盘" in prompt:
        return "复盘摘要：本次预警发布较及时，游客版文案具备明确避险动作。改进建议：提前核查安置点开放状态和估算承载，推送后同步检查语音播报覆盖率，并对高风险点增加二次确认巡查。"
    if "索道" in prompt:
        return "遇到强降雨、雷电或大风时，天门山索道可能临时限流或停运。请以景区现场公告为准，优先停留在游客中心、索道站等室内区域，不要在临崖步道逗留。"
    if "道路" in prompt:
        return "遇到道路中断时，请不要自行穿越积水或落石路段。打开预警详情查看最近安置点，并听从交警和景区工作人员引导绕行。"
    if "事件摘要" in prompt or "现场事件" in prompt:
        return "事件摘要：现场存在游客滞留或通行风险。风险判断：需尽快核实人数、位置和周边边坡/水位变化。建议行动：派出就近巡查人员，开启广播提醒，准备最近安置点和医疗转运资源。"
    return "暴雨来临时，请远离溪谷、陡坡、临崖步道和低洼地带，优先前往游客中心、村部或标注安置点。若收到转移通知，应立即携带必要物品有序撤离。"
