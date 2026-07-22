import json

from sqlalchemy import select

from backend.database import create_all, session_scope
from backend.db_models import AlertDB, BroadcastRecordDB, IncidentDB, MessageDB, ShelterDB
from backend.models import now_iso
from backend.services.storage import DISASTER_POINTS_FILE, SHELTERS_FILE, read_json, write_json


SRC_ZRZY = "张家界市自然资源和规划局公开地质灾害巡排查信息"
SRC_CMA = "张家界市气象局公开暴雨预警信息"
SRC_GOV = "张家界市公开防汛和转移避险信息"
SRC_TOUR = "张家界市景区公开游客服务和安全提示信息"


DISASTER_POINTS = [
    ("zjj-yd-luoshui", "永定区罗水乡大明村向家组滑坡巡查点", "永定区", "罗水乡大明村", 29.2105, 110.3568, 32, 1, SRC_ZRZY),
    ("zjj-sz-yuanzicun", "桑植县上洞街乡院子村张家湾组滑坡风险点", "桑植县", "上洞街乡院子村", 29.5827, 110.1824, 34, 2, SRC_ZRZY),
    ("zjj-yd-xinqiao", "永定区新桥镇远大村塔圣岗组山体滑坡点", "永定区", "新桥镇远大村", 29.1584, 110.6253, 31, 1, SRC_ZRZY),
    ("zjj-cl-changtanhe", "慈利县金慈街道长潭河村泥石流风险点", "慈利县", "金慈街道长潭河村", 29.4019, 111.1174, 28, 1, SRC_GOV),
    ("zjj-wly-rain", "武陵源区暴雨致灾风险监测区", "武陵源区", "武陵源区", 29.3457, 110.5488, 30, 1, SRC_CMA),
]

SHELTERS = [
    ("zjj-safe-cl-changtanhe", "慈利县金慈街道长潭河村村部安全点", "慈利县金慈街道长潭河村", 29.4019, 111.1174, 130, "金慈街道/长潭河村", "湖南省自然资源厅2024-04-02公开避险案例披露转移安置130名群众"),
    ("zjj-safe-sz-yuanzicun", "桑植县上洞街乡院子村转移避险安置点", "桑植县上洞街乡院子村", 29.5827, 110.1824, 60, "上洞街乡/院子村", f"{SRC_GOV}；容量按村级临时安置点口径估算"),
    ("zjj-safe-wly-weather", "武陵源区暴雨预警临时避雨安全点", "武陵源区", 29.3457, 110.5488, 260, "武陵源区防汛值守力量", "地点按景区暴雨预警疏导流程设置；容量按游客短时避雨和分批转运口径估算"),
    ("zjj-safe-tianmenshan", "天门山景区游客应急服务点", "永定区", 29.1169, 110.4784, 240, "景区游客服务点", f"{SRC_TOUR}；容量按索道站周边短时避险和疏导口径估算"),
]

ALERTS = [
    ("张家界市暴雨黄色预警测试", "暴雨", "黄色", ["武陵源区"], "武陵源区需防范强降雨致灾风险。", SRC_CMA),
    ("张家界市强降雨地灾巡查提示", "暴雨/地质灾害", "橙色", ["永定区", "桑植县", "慈利县"], "重点关注隐患点、风险区和切坡建房户。", SRC_ZRZY),
    ("张家界市山洪易发区巡查提示", "山洪/洪水", "黄色", ["张家界市"], "强降雨期间对山洪易发区和隐患点开展驻点巡查监测。", SRC_GOV),
    ("张家界市游客分流与安全提示", "景区客流/游客安全", "黄色", ["武陵源区", "天门山景区"], "引导游客避开高风险区域，关注景区提示和天气预警。", SRC_TOUR),
    ("张家界市旅游求助提示", "医疗/SOS", "蓝色", ["武陵源区", "天门山景区"], "游客突发不适或受伤时，优先联系景区服务点和现场工作人员。", SRC_TOUR),
]

INCIDENTS = [
    ("landslide", "张家界公开案例：桑植县上洞街乡院子村张家湾组滑坡风险，受威胁群众转移避险安置。", 29.5827, 110.1824, "桑植县", "院子村张家湾组", "上洞街乡院子村", "responding", "medium"),
    ("landslide", "张家界公开案例：永定区罗水乡大明村向家组滑坡巡查监测事件。", 29.2105, 110.3568, "永定区", "大明村向家组", "罗水乡大明村", "pending", "medium"),
    ("landslide", "张家界公开案例：永定区新桥镇远大村塔圣岗组山体滑坡，已提前转移避险。", 29.1584, 110.6253, "永定区", "远大村塔圣岗组", "新桥镇远大村", "resolved", "high"),
    ("flood", "张家界公开案例：慈利县金慈街道长潭河村短时强降雨诱发山洪泥石流风险，群众转移到村部等安全地点。", 29.4019, 111.1174, "慈利县", "长潭河村", "金慈街道", "resolved", "critical"),
    ("medical", "张家界景区服务测试：天门山景区游客突发不适，联动景区服务点开展现场处置。", 29.1169, 110.4784, "永定区", None, "天门山景区", "responding", "medium"),
]

MESSAGES = [
    ("暴雨黄色预警触达", "张家界市气象局暴雨预警触达测试，请武陵源区注意强降雨致灾风险。", ["resident", "tourist", "community_admin"]),
    ("地灾隐患点巡查提醒", "请基层干部对隐患点、风险区和切坡建房户开展巡查，发现变形迹象及时上报。", ["community_admin", "county_admin"]),
    ("转移避险安置提醒", "遇山洪、滑坡、泥石流风险时，请按现场干部指引前往村部等安全地点。", ["resident", "tourist"]),
    ("游客求助处置提醒", "游客身体不适、迷路或遇险时，请联系景区服务点、现场工作人员或提交SOS。", ["tourist", "resident"]),
    ("我的张家界平台触达测试", "本消息用于测试天气预警、系统消息、市民随手拍和位置服务闭环。", ["resident", "tourist"]),
]

BROADCASTS = [
    ("暴雨预警广播", "张家界市气象局发布暴雨预警，请远离低洼地带、临崖道路和山洪沟道。"),
    ("地灾巡查广播", "请各村组巡查员关注滑坡、崩塌、泥石流和切坡建房风险，发现异常立即上报。"),
    ("转移避险广播", "收到转移指令后，请携带必要物品前往村部等安全地点，不要返回危险区域。"),
    ("景区游客安全广播", "游客请关注景区提示和天气预警，避免进入临崖、涉水、封闭或限流区域。"),
    ("SOS求助广播", "如遇受伤、迷路、被困等紧急情况，请立即联系现场工作人员或使用SOS求助。"),
]


def upsert_json(path, rows):
    existing = read_json(path, [])
    by_id = {item["id"]: item for item in existing if "id" in item}
    for item in rows:
        by_id[item["id"]] = item
    write_json(path, list(by_id.values()))


def seed_files():
    upsert_json(
        DISASTER_POINTS_FILE,
        [
            {
                "id": id_,
                "name": name,
                "district": district,
                "scenic_area": area,
                "lat": lat,
                "lng": lng,
                "slope": slope,
                "lithology": "张家界公开资料对应的前端测试落点",
                "historical_landslide": history,
                "source": source,
                "reference_url": "https://www.zjj.gov.cn/",
            }
            for id_, name, district, area, lat, lng, slope, history, source in DISASTER_POINTS
        ],
    )
    upsert_json(
        SHELTERS_FILE,
        [
            {
                "id": id_,
                "name": name,
                "area": area,
                "lat": lat,
                "lng": lng,
                "capacity": capacity,
                "contact": contact,
                "source": source,
            }
            for id_, name, area, lat, lng, capacity, contact, source in SHELTERS
        ],
    )


def seed_db():
    create_all()
    with session_scope() as db:
        for id_, name, area, lat, lng, capacity, contact, source in SHELTERS:
            payload = dict(id=id_, name=name, area=area, lat=lat, lng=lng, capacity=capacity, contact=contact, source=source)
            record = db.get(ShelterDB, id_)
            if record:
                for key, value in payload.items():
                    setattr(record, key, value)
            else:
                db.add(ShelterDB(**payload))

        for title, dtype, level, areas, advice, source in ALERTS:
            payload = {
                "title": title,
                "disaster_type": dtype,
                "level": level,
                "affected_areas": json.dumps(areas, ensure_ascii=False),
                "started_at": "2026-05-31 20:00",
                "duration": "张家界公开资料测试数据",
                "advice": advice,
                "status": "active",
                "data_source_note": source,
                "audience_messages": json.dumps({"resident": advice, "tourist": advice, "village_officer": advice, "scenic_manager": advice}, ensure_ascii=False),
                "created_at": now_iso(),
                "is_pushed": True,
                "pushed_at": now_iso(),
            }
            record = db.scalar(select(AlertDB).where(AlertDB.title == title))
            if record:
                for key, value in payload.items():
                    setattr(record, key, value)
            else:
                db.add(AlertDB(**payload))

        for type_, desc, lat, lng, district, community, area, status, severity in INCIDENTS:
            nearest = SHELTERS[0]
            payload = {
                "type": type_,
                "description": desc,
                "lat": lat,
                "lng": lng,
                "district": district,
                "community": community,
                "scenic_area": area,
                "severity": severity,
                "status": status,
                "reporter_role": "tourist" if type_ == "medical" else "community_admin",
                "reporter_id": 1,
                "nearest_shelter": json.dumps({"id": nearest[0], "name": nearest[1], "area": nearest[2], "lat": nearest[3], "lng": nearest[4], "capacity": nearest[5], "distance_km": 0.5}, ensure_ascii=False),
                "need_review": type_ == "medical",
                "is_demo": True,
                "created_at": now_iso(),
                "resolved_at": now_iso() if status == "resolved" else None,
            }
            record = db.scalar(select(IncidentDB).where(IncidentDB.description == desc))
            if record:
                for key, value in payload.items():
                    setattr(record, key, value)
            else:
                db.add(IncidentDB(**payload))

        for title, content, roles in MESSAGES:
            payload = {
                "title": title,
                "content": content,
                "target_roles": json.dumps(roles, ensure_ascii=False),
                "target_district": None,
                "target_community": None,
                "sender_id": 1,
                "sender_role": "city_admin",
                "priority": "city",
                "source_type": "zjj_official_test_seed",
                "related_id": None,
                "created_at": now_iso(),
            }
            record = db.scalar(select(MessageDB).where(MessageDB.title == title))
            if record:
                for key, value in payload.items():
                    setattr(record, key, value)
            else:
                db.add(MessageDB(**payload))

        for title, content in BROADCASTS:
            payload = {
                "alert_id": 0,
                "alert_title": title,
                "audience": "张家界市居民、游客、基层干部",
                "content": content,
                "type": "张家界公开资料测试播报",
                "source_type": "zjj_official_test_seed",
                "play_count": 0,
                "created_at": now_iso(),
            }
            record = db.scalar(select(BroadcastRecordDB).where(BroadcastRecordDB.alert_title == title))
            if record:
                for key, value in payload.items():
                    setattr(record, key, value)
            else:
                db.add(BroadcastRecordDB(**payload))


if __name__ == "__main__":
    seed_files()
    seed_db()
    print("zjj-official-test-data-seeded")
