from typing import Any, Dict

import requests

from backend.config import get_settings


AMAP_ZHANGJIAJIE_ADCODE = "430800"
WEEK_LABELS = {
    "1": "周一",
    "2": "周二",
    "3": "周三",
    "4": "周四",
    "5": "周五",
    "6": "周六",
    "7": "周日",
}


def get_current_weather() -> Dict[str, Any]:
    settings = get_settings()

    if settings.amap_weather_key:
        try:
            return _get_amap_weather(settings.amap_weather_key)
        except Exception as exc:
            qweather = _get_qweather(settings.weather_api_key, settings.qweather_location_id)
            if qweather:
                qweather["note"] = f"高德天气 API 暂不可用，已切换和风天气：{exc}"
                return qweather
            return _fallback_weather(f"高德天气 API 暂不可用，已切换历史仿真数据：{exc}")

    qweather = _get_qweather(settings.weather_api_key, settings.qweather_location_id)
    if qweather:
        return qweather

    return _fallback_weather("未配置 AMAP_WEATHER_KEY，使用历史降雨场景仿真")


def _get_amap_weather(key: str) -> Dict[str, Any]:
    live_response = requests.get(
        "https://restapi.amap.com/v3/weather/weatherInfo",
        params={"city": AMAP_ZHANGJIAJIE_ADCODE, "key": key, "extensions": "base"},
        timeout=8,
    )
    forecast_response = requests.get(
        "https://restapi.amap.com/v3/weather/weatherInfo",
        params={"city": AMAP_ZHANGJIAJIE_ADCODE, "key": key, "extensions": "all"},
        timeout=8,
    )
    live_response.raise_for_status()
    forecast_response.raise_for_status()
    live_data = live_response.json()
    forecast_data = forecast_response.json()

    if live_data.get("status") != "1":
        raise ValueError(live_data.get("info") or "AMap live weather request failed")
    if forecast_data.get("status") != "1":
        raise ValueError(forecast_data.get("info") or "AMap forecast request failed")

    live = (live_data.get("lives") or [{}])[0]
    forecast = (forecast_data.get("forecasts") or [{}])[0]
    casts = forecast.get("casts") or []
    today = casts[0] if casts else {}
    weather_text = live.get("weather") or today.get("dayweather") or "天气实况"
    temperature = _safe_float(live.get("temperature"), 0.0)
    humidity = _safe_float(live.get("humidity"), None)
    rainfall_24h = _estimate_rainfall_24h(
        weather_text,
        today.get("dayweather") or "",
        today.get("nightweather") or "",
    )
    forecast_days = [_amap_forecast_day(cast, humidity if index == 0 else None) for index, cast in enumerate(casts)]

    summary = f"{weather_text}，实时 {round(temperature or 0, 1)}℃"
    if humidity is not None:
        summary += f"，湿度 {round(humidity)}%"
    if rainfall_24h > 0:
        summary += f"，降雨估算 {round(rainfall_24h, 1)} mm"

    return {
        "city": live.get("city") or forecast.get("city") or "张家界市",
        "adcode": live.get("adcode") or forecast.get("adcode") or AMAP_ZHANGJIAJIE_ADCODE,
        "province": live.get("province") or forecast.get("province") or "湖南省",
        "text": weather_text,
        "temperature": round(temperature or 0, 1),
        "humidity": humidity,
        "wind_direction": live.get("winddirection"),
        "wind_power": live.get("windpower"),
        "precip_now": 0.0,
        "rainfall_24h": round(rainfall_24h, 1),
        "summary": summary,
        "source": "高德地图天气 API",
        "simulated": False,
        "rainfall_estimated": True,
        "forecast_days": forecast_days,
        "updated_at": live.get("reporttime") or forecast.get("reporttime"),
        "forecast_updated_at": forecast.get("reporttime"),
        "data_note": "高德天气预报接口提供天气现象、温度和风力；降雨量为依据天气现象的风险估算值，实时湿度来自实况接口。",
    }


def _amap_forecast_day(cast: dict[str, Any], humidity: float | None) -> dict[str, Any]:
    day_weather = cast.get("dayweather") or "暂无"
    night_weather = cast.get("nightweather") or "暂无"
    day_temp = _safe_float(cast.get("daytemp"), None)
    night_temp = _safe_float(cast.get("nighttemp"), None)
    rainfall = _estimate_rainfall_24h(day_weather, night_weather)
    return {
        "date": cast.get("date"),
        "week": cast.get("week"),
        "week_label": WEEK_LABELS.get(str(cast.get("week")), f"周{cast.get('week') or '-'}"),
        "day_weather": day_weather,
        "night_weather": night_weather,
        "day_temp": day_temp,
        "night_temp": night_temp,
        "temp_range": _temp_range(day_temp, night_temp),
        "day_wind": cast.get("daywind") or "暂无",
        "night_wind": cast.get("nightwind") or "暂无",
        "day_power": cast.get("daypower") or "暂无",
        "night_power": cast.get("nightpower") or "暂无",
        "humidity": humidity,
        "precipitation": round(rainfall, 1),
        "rainfall_estimated": True,
    }


def _get_qweather(key: str, location_id: str) -> Dict[str, Any] | None:
    if not key:
        return None
    try:
        hourly_response = requests.get(
            "https://devapi.qweather.com/v7/weather/24h",
            params={"location": location_id, "key": key},
            timeout=8,
        )
        now_response = requests.get(
            "https://devapi.qweather.com/v7/weather/now",
            params={"location": location_id, "key": key},
            timeout=8,
        )
        hourly_response.raise_for_status()
        now_response.raise_for_status()
        hourly_data = hourly_response.json()
        now_data = now_response.json()
        hourly = hourly_data.get("hourly", [])
        now = now_data.get("now", {})
        rainfall_24h = sum(float(item.get("precip", 0) or 0) for item in hourly)
        precip_now = float(now.get("precip", 0) or 0)
        weather_text = now.get("text") or "天气实况"
        temperature = float(now.get("temp", 0) or 0)
        humidity = _safe_float(now.get("humidity"), None)
        return {
            "city": "张家界市",
            "text": weather_text,
            "temperature": round(temperature, 1),
            "humidity": humidity,
            "precip_now": round(precip_now, 1),
            "rainfall_24h": round(rainfall_24h, 1),
            "summary": f"{weather_text}，实时 {round(temperature, 1)}℃，当前降雨 {round(precip_now, 1)} mm",
            "source": "和风天气 API",
            "simulated": False,
            "forecast_days": [],
            "updated_at": now_data.get("updateTime"),
        }
    except Exception:
        return None


def _estimate_rainfall_24h(*weather_texts: str) -> float:
    joined = " ".join(text for text in weather_texts if text)
    if any(word in joined for word in ["大暴雨", "特大暴雨"]):
        return 120.0
    if "暴雨" in joined:
        return 85.0
    if "大雨" in joined:
        return 38.0
    if "中雨" in joined:
        return 18.0
    if any(word in joined for word in ["雷阵雨", "阵雨", "小雨", "雨"]):
        return 8.0
    return 0.0


def _temp_range(day_temp: float | None, night_temp: float | None) -> str:
    values = [value for value in [night_temp, day_temp] if value is not None]
    if not values:
        return "--"
    return f"{min(values):.0f}-{max(values):.0f}℃"


def _safe_float(value: Any, fallback: float | None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _fallback_weather(note: str) -> Dict[str, Any]:
    forecast_days = [
        {
            "date": "今日",
            "week_label": "今日",
            "day_weather": "中到大雨",
            "night_weather": "阵雨",
            "day_temp": 24,
            "night_temp": 20,
            "temp_range": "20-24℃",
            "day_wind": "东北风",
            "night_wind": "东北风",
            "day_power": "3级",
            "night_power": "3级",
            "humidity": 92,
            "precipitation": 68.5,
            "rainfall_estimated": True,
        }
    ]
    return {
        "city": "张家界市",
        "text": "中到大雨",
        "temperature": 22.0,
        "humidity": 92,
        "precip_now": 8.6,
        "rainfall_24h": 68.5,
        "summary": "武陵源、天门山一带有中到大雨，局地短时强降雨",
        "source": "基于历史强降雨预警场景模拟",
        "simulated": True,
        "forecast_days": forecast_days,
        "note": note,
    }
