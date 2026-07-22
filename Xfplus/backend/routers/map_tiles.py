import hashlib
import math

from fastapi import APIRouter, Query
import requests

from backend.config import get_settings

router = APIRouter(prefix="/api/map", tags=["map"])

ZHANGJIAJIE_BOUNDS = {
    "min_lng": 109.7,
    "min_lat": 28.6,
    "max_lng": 111.3,
    "max_lat": 30.0,
}
ZHANGJIAJIE_CENTER = {"lat": 29.1171, "lng": 110.4792}
DISTRICT_CENTERS = {
    "永定区": {"lat": 29.1171, "lng": 110.4792},
    "武陵源区": {"lat": 29.3472, "lng": 110.5587},
    "慈利县": {"lat": 29.4297, "lng": 111.1397},
    "桑植县": {"lat": 29.3999, "lng": 110.1641},
}
OFFICIAL_SCENIC_COORDINATES = [
    ("张家界国家森林公园", "武陵源区", 29.3335, 110.4446),
    ("森林公园", "武陵源区", 29.3335, 110.4446),
    ("老磨湾", "武陵源区", 29.3335, 110.4446),
    ("武陵源游客中心", "武陵源区", 29.3472, 110.5587),
    ("武陵源标志门", "武陵源区", 29.3490, 110.5560),
    ("标志门", "武陵源区", 29.3490, 110.5560),
    ("金鞭溪", "武陵源区", 29.3472, 110.5587),
    ("黄龙洞", "武陵源区", 29.3618, 110.6284),
    ("宝峰湖", "武陵源区", 29.3410, 110.5660),
    ("天子山", "武陵源区", 29.3710, 110.4730),
    ("袁家界", "武陵源区", 29.3530, 110.4590),
    ("杨家界", "武陵源区", 29.3690, 110.4210),
    ("黄石寨", "武陵源区", 29.3160, 110.4360),
    ("十里画廊", "武陵源区", 29.3680, 110.5640),
    ("天门山索道", "永定区", 29.1160, 110.4749),
    ("天门山", "永定区", 29.1167, 110.4759),
    ("张家界大峡谷", "慈利县", 29.3939, 110.6938),
    ("大峡谷", "慈利县", 29.3939, 110.6938),
    ("玻璃桥", "慈利县", 29.3939, 110.6938),
]
KNOWN_ZHANGJIAJIE_LOCATIONS = [
    ("张家界荷花", "永定区", 29.1028, 110.4434),
    ("荷花机场", "永定区", 29.1028, 110.4434),
    ("张家界西站", "永定区", 29.1782, 110.4243),
    ("高铁站", "永定区", 29.1782, 110.4243),
    ("张家界站", "永定区", 29.1098, 110.4866),
    ("火车站", "永定区", 29.1098, 110.4866),
    ("天门山索道", "永定区", 29.1160, 110.4749),
    ("天门山", "永定区", 29.1167, 110.4759),
    ("大庸古城", "永定区", 29.1262, 110.4789),
    ("大庸桥", "永定区", 29.1242, 110.4509),
    ("南庄坪", "永定区", 29.1192, 110.4725),
    ("崇文", "永定区", 29.1280, 110.4885),
    ("沙堤", "永定区", 29.1912, 110.4390),
    ("阳湖坪", "永定区", 29.0910, 110.5210),
    ("张家界国家森林公园", "武陵源区", 29.3335, 110.4446),
    ("森林公园", "武陵源区", 29.3335, 110.4446),
    ("老磨湾", "武陵源区", 29.3335, 110.4446),
    ("武陵源标志门", "武陵源区", 29.3490, 110.5560),
    ("标志门", "武陵源区", 29.3490, 110.5560),
    ("武陵源游客中心", "武陵源区", 29.3472, 110.5587),
    ("袁家界", "武陵源区", 29.3530, 110.4590),
    ("杨家界", "武陵源区", 29.3690, 110.4210),
    ("天子山", "武陵源区", 29.3710, 110.4730),
    ("黄石寨", "武陵源区", 29.3160, 110.4360),
    ("金鞭溪", "武陵源区", 29.3472, 110.5587),
    ("水绕四门", "武陵源区", 29.3400, 110.5370),
    ("十里画廊", "武陵源区", 29.3680, 110.5640),
    ("宝峰湖", "武陵源区", 29.3410, 110.5660),
    ("黄龙洞", "武陵源区", 29.3618, 110.6284),
    ("溪布街", "武陵源区", 29.3452, 110.5550),
    ("张家界大峡谷", "慈利县", 29.3939, 110.6938),
    ("大峡谷", "慈利县", 29.3939, 110.6938),
    ("玻璃桥", "慈利县", 29.3939, 110.6938),
    ("慈利县城", "慈利县", 29.4297, 111.1397),
    ("零阳", "慈利县", 29.4297, 111.1397),
    ("金慈", "慈利县", 29.4019, 111.1174),
    ("江垭", "慈利县", 29.5860, 111.2060),
    ("五雷山", "慈利县", 29.5200, 111.0600),
    ("万福温泉", "慈利县", 29.5000, 111.2600),
    ("桑植县城", "桑植县", 29.3999, 110.1641),
    ("澧源", "桑植县", 29.3999, 110.1641),
    ("洪家关", "桑植县", 29.4610, 110.1340),
    ("贺龙", "桑植县", 29.4610, 110.1340),
    ("九天洞", "桑植县", 29.5700, 110.2230),
    ("上洞街", "桑植县", 29.5827, 110.1824),
    ("芙蓉桥", "桑植县", 29.5300, 110.0800),
]
DISTRICT_KEYWORDS = {
    "永定区": ["永定", "市区", "荷花", "天门山", "大庸", "南庄坪", "崇文", "沙堤", "阳湖坪", "罗水", "新桥"],
    "武陵源区": ["武陵源", "森林公园", "袁家界", "杨家界", "天子山", "黄石寨", "金鞭溪", "宝峰湖", "黄龙洞", "溪布街", "标志门"],
    "慈利县": ["慈利", "大峡谷", "玻璃桥", "江垭", "五雷山", "万福", "零阳", "金慈"],
    "桑植县": ["桑植", "洪家关", "贺龙", "九天洞", "上洞街", "芙蓉桥", "澧源"],
}


def _inside_zhangjiajie(lat: float, lng: float) -> bool:
    return (
        ZHANGJIAJIE_BOUNDS["min_lat"] <= lat <= ZHANGJIAJIE_BOUNDS["max_lat"]
        and ZHANGJIAJIE_BOUNDS["min_lng"] <= lng <= ZHANGJIAJIE_BOUNDS["max_lng"]
    )


def _parse_lonlat(value: str | None) -> tuple[float, float] | None:
    if not value:
        return None
    try:
        lng_text, lat_text = value.split(",", 1)
        lng = float(lng_text)
        lat = float(lat_text)
    except (TypeError, ValueError):
        return None
    if not _inside_zhangjiajie(lat, lng):
        return None
    return lat, lng


def _out_of_china(lat: float, lng: float) -> bool:
    return lng < 72.004 or lng > 137.8347 or lat < 0.8293 or lat > 55.8271


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def _wgs84_to_gcj02(lat: float, lng: float) -> tuple[float, float]:
    if _out_of_china(lat, lng):
        return lat, lng
    a = 6378245.0
    ee = 0.00669342162296594323
    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - ee * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (a / sqrtmagic * math.cos(radlat) * math.pi)
    return lat + dlat, lng + dlng


def _gcj02_to_wgs84(lat: float, lng: float) -> tuple[float, float]:
    if _out_of_china(lat, lng):
        return lat, lng
    gcj_lat, gcj_lng = _wgs84_to_gcj02(lat, lng)
    return lat * 2 - gcj_lat, lng * 2 - gcj_lng


def _infer_district(query: str, district: str | None) -> str:
    if district in DISTRICT_CENTERS:
        return district or "张家界市"
    for name in DISTRICT_CENTERS:
        if name in query:
            return name
    for name, keywords in DISTRICT_KEYWORDS.items():
        if any(keyword in query for keyword in keywords):
            return name
    return "张家界市"


def _hash_offset(query: str, lat_radius: float, lng_radius: float) -> tuple[float, float]:
    digest = hashlib.sha256(query.encode("utf-8")).digest()
    lat_unit = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    lng_unit = int.from_bytes(digest[4:8], "big") / 0xFFFFFFFF
    return (lat_unit - 0.5) * lat_radius * 2, (lng_unit - 0.5) * lng_radius * 2


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(value, max_value))


def _fallback_location(query: str, district: str | None) -> dict:
    for keyword, known_district, lat, lng in OFFICIAL_SCENIC_COORDINATES:
        if keyword in query:
            return {
                "name": query,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "district": known_district,
                "source": "official_scenic",
                "precise": True,
            }

    for keyword, known_district, lat, lng in KNOWN_ZHANGJIAJIE_LOCATIONS:
        if keyword in query:
            return {
                "name": query,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "district": known_district,
                "source": "local",
                "precise": True,
            }

    inferred_district = _infer_district(query, district)
    center = DISTRICT_CENTERS.get(inferred_district, ZHANGJIAJIE_CENTER)
    lat_offset, lng_offset = _hash_offset(query, 0.055 if inferred_district != "张家界市" else 0.22, 0.075 if inferred_district != "张家界市" else 0.35)
    lat = _clamp(center["lat"] + lat_offset, ZHANGJIAJIE_BOUNDS["min_lat"], ZHANGJIAJIE_BOUNDS["max_lat"])
    lng = _clamp(center["lng"] + lng_offset, ZHANGJIAJIE_BOUNDS["min_lng"], ZHANGJIAJIE_BOUNDS["max_lng"])

    return {
        "name": query,
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "district": inferred_district,
        "source": "estimated",
        "precise": False,
    }



def _amap_search(query: str, district: str | None, key: str) -> dict | None:
    keywords = []
    cleaned = query.strip()
    if district:
        keywords.append(f"张家界市{district}{cleaned}")
    keywords.extend([f"张家界市{cleaned}", cleaned])

    seen = set()
    for keyword in keywords:
        if keyword in seen:
            continue
        seen.add(keyword)
        response = requests.get(
            "https://restapi.amap.com/v3/place/text",
            params={
                "key": key,
                "keywords": keyword,
                "city": "张家界",
                "citylimit": "true",
                "offset": 10,
                "page": 1,
                "extensions": "base",
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "1":
            continue
        for poi in payload.get("pois") or []:
            location = poi.get("location") or ""
            try:
                lng_text, lat_text = location.split(",", 1)
                gcj_lng = float(lng_text)
                gcj_lat = float(lat_text)
            except (TypeError, ValueError):
                continue
            lat, lng = _gcj02_to_wgs84(gcj_lat, gcj_lng)
            if not _inside_zhangjiajie(lat, lng):
                continue
            return {
                "name": poi.get("name") or cleaned,
                "lat": round(lat, 6),
                "lng": round(lng, 6),
                "district": poi.get("adname") or district or "",
                "address": poi.get("address") or "",
                "source": "amap",
                "precise": True,
            }
    return None



@router.get('/geocode')
def geocode_location(
    q: str = Query(..., min_length=1, max_length=120),
    district: str | None = Query(default=None, max_length=40),
):
    settings = get_settings()
    query = q.strip()
    if not query:
        return _fallback_location("张家界市", district)

    official_match = _fallback_location(query, district)
    if official_match["source"] == "official_scenic":
        return official_match

    if settings.amap_server_key:
        try:
            match = _amap_search(query, district, settings.amap_server_key)
            if match:
                return match
        except (requests.RequestException, ValueError, KeyError):
            pass


    return official_match
