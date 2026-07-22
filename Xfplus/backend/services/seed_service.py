import hashlib
import json
import secrets

from sqlalchemy import delete, select

from backend.database import create_all, session_scope
from backend.db_models import AlertDB, IncidentDB, MessageDB, ShelterDB, UserDB
from backend.models import now_iso
from backend.services.storage import ALERTS_FILE, DATA_DIR, INCIDENTS_FILE, SHELTERS_FILE, read_json


def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256(f"{salt}:{password}".encode("utf-8")).hexdigest()


def initialize_database() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    create_all()
    seed_users()
    seed_shelters()
    seed_alerts()
    seed_incidents()
    seed_public_suggestions()


PUBLIC_SUGGESTION_DEMO_DATA = [
    {
        "title": "金鞭溪步道临水护栏松动",
        "content": "金鞭溪靠近老磨湾方向有一段临水护栏晃动明显，雨后游客通行较多，建议尽快安排巡检并设置临时提醒牌。",
        "sender_id": 5,
        "sender_role": "tourist",
        "target_district": "武陵源区",
        "target_community": "金鞭溪景区",
        "status": "pending_review",
        "created_at": "2026-06-05T09:18:00",
    },
    {
        "title": "标志门社区排水沟淤堵",
        "content": "标志门社区停车场旁排水沟被落叶和淤泥堵住，强降雨时积水漫到人行道，建议雨前清淤。",
        "sender_id": 4,
        "sender_role": "resident",
        "target_district": "武陵源区",
        "target_community": "标志门社区",
        "status": "replied",
        "reply_content": "已安排社区网格员和环卫人员下午现场清理，清淤完成后将在站内同步结果。",
        "review_note": "属地社区先行处理，区县应急办跟踪复核。",
        "reviewed_by": 1,
        "reviewed_at": "2026-06-05T10:05:00",
        "created_at": "2026-06-05T08:42:00",
    },
    {
        "title": "大峡谷游客中心指示牌不清晰",
        "content": "大峡谷游客中心到临时避险集合点的指示牌被树枝遮挡，外地游客不容易识别，建议补充夜间反光标识。",
        "sender_id": 5,
        "sender_role": "tourist",
        "target_district": "慈利县",
        "target_community": "大峡谷游客中心",
        "status": "forwarded",
        "review_note": "转派景区管理人员核查标识遮挡和夜间引导问题。",
        "reviewed_by": 1,
        "reviewed_at": "2026-06-05T11:12:00",
        "created_at": "2026-06-05T08:10:00",
    },
    {
        "title": "天门山索道站排队区遮雨不足",
        "content": "索道站排队区遇到短时强降雨时遮雨空间不足，老人和儿童容易拥挤，建议增设临时雨棚和分流提示。",
        "sender_id": 5,
        "sender_role": "tourist",
        "target_district": "永定区",
        "target_community": "天门山索道站",
        "status": "closed",
        "reply_content": "景区已增设临时雨棚和分流隔离带，并安排工作人员在强降雨时段引导游客进入室内候客区。",
        "review_note": "整改完成，保留后续复查。",
        "reviewed_by": 1,
        "reviewed_at": "2026-06-05T12:20:00",
        "created_at": "2026-06-05T07:55:00",
    },
    {
        "title": "溪布街低洼路段夜间照明不足",
        "content": "溪布街靠近低洼排水口的路段夜间灯光偏暗，雨天积水不容易发现，建议增加警示灯或反光锥桶。",
        "sender_id": 4,
        "sender_role": "resident",
        "target_district": "武陵源区",
        "target_community": "溪布街社区",
        "status": "pending_review",
        "created_at": "2026-06-05T07:30:00",
    },
]


OFFICIAL_INCIDENTS = [
    {
        "type": "flood",
        "description": "2024年3月31日，慈利县金慈街道长潭河村突发暴雨形成泥石流；当地根据预警和巡排查结果，提前转移安置130名群众，未造成人员伤亡。",
        "lat": 29.4019,
        "lng": 111.1174,
        "district": "慈利县",
        "community": "长潭河村",
        "scenic_area": "金慈街道长潭河村",
        "severity": "critical",
        "status": "resolved",
        "reporter_role": "county_admin",
        "nearest_shelter_id": "zjj-safe-cl-changtanhe",
        "source_title": "张家界：慈利县130人紧急转移 成功避险泥石流灾害",
        "source_org": "湖南省自然资源厅",
        "source_url": "https://zrzyt.hunan.gov.cn/zrzyt/xxgk/gzdt/sxxx/202404/t20240402_33268697.html",
        "source_date": "2024-04-02",
        "created_at": "2024-03-31T00:30:00",
        "resolved_at": "2024-03-31T01:10:00",
        "workflow_steps": [
            "气象台发布暴雨橙色预警，县级组织会商研判。",
            "自然资源、街道和村组开展巡排查，连续发送预警信息。",
            "发现泥石流苗头后按预案转移群众至村部及周边安全住户。",
            "清点130名转移群众并持续巡查受灾房屋、道路和沟道。",
        ],
    },
    {
        "type": "landslide",
        "description": "2025年5月22日，慈利县金岩土家族乡红联村7组发生山体滑坡，滑坡方量约1.8万立方米；巡查发现隐患后提前转移10户18人，未造成人员伤亡。",
        "lat": 29.6563,
        "lng": 110.9182,
        "district": "慈利县",
        "community": "红联村7组",
        "scenic_area": "金岩土家族乡红联村",
        "severity": "high",
        "status": "resolved",
        "reporter_role": "county_admin",
        "nearest_shelter_id": "zjj-safe-cl-changtanhe",
        "source_title": "张家界：10户18人及时转移！慈利县金岩乡成功避让一起滑坡地质灾害",
        "source_org": "湖南省自然资源厅",
        "source_url": "https://zrzyt.hunan.gov.cn/xxgk/gzdt/sxxx/202505/t20250523_33680533.html",
        "source_date": "2025-05-23",
        "created_at": "2025-05-22T10:30:00",
        "resolved_at": "2025-05-22T15:30:00",
        "workflow_steps": [
            "省市县发布气象预警和地质灾害短临预警。",
            "乡镇启动地质灾害应急预案，自然资源所协同镇政府巡排查。",
            "10时30分发现滑坡隐患，11时20分完成10户18人转移。",
            "县自然资源局会同专家踏勘，设置警示牌、警戒线并安排专人监测。",
        ],
    },
    {
        "type": "landslide",
        "description": "2025年6月18日至19日强降雨期间，慈利县三合镇雷岩村11组房屋后出现山体滑坡风险；村支两委巡查上报后，2名受威胁群众转移至村部。",
        "lat": 29.4142,
        "lng": 110.9924,
        "district": "慈利县",
        "community": "雷岩村11组",
        "scenic_area": "三合镇雷岩村",
        "severity": "high",
        "status": "resolved",
        "reporter_role": "community_admin",
        "nearest_shelter_id": "zjj-safe-cl-changtanhe",
        "source_title": "迎战强降雨！紧急转移群众保安全",
        "source_org": "湖南省应急管理厅",
        "source_url": "https://yjt.hunan.gov.cn/yjt/tszt/ywzl/fxkz/202506/t20250620_33718940.html",
        "source_date": "2025-06-20",
        "created_at": "2025-06-18T18:52:00",
        "resolved_at": "2025-06-19T06:30:00",
        "workflow_steps": [
            "村支两委通过微信群、电话发布强降雨信息。",
            "巡查发现屋后土质松散并有滑坡风险，立即上报镇级。",
            "镇村干部赶到现场，将2名群众转移至村部并安抚群众。",
            "次日滑坡发生后复核人员安全，继续加强周边巡查。",
        ],
    },
    {
        "type": "landslide",
        "description": "2025年6月19日，桑植县上河溪乡云雾山村巡查发现住户屋前坡面来水夹带浑浊泥土，存在滑坡风险；1户3人被及时转移，随后坡体发生约2.5万立方米滑坡。",
        "lat": 29.7092,
        "lng": 110.1546,
        "district": "桑植县",
        "community": "云雾山村",
        "scenic_area": "上河溪乡云雾山村",
        "severity": "critical",
        "status": "resolved",
        "reporter_role": "community_admin",
        "nearest_shelter_id": "zjj-safe-sz-yuanzicun",
        "source_title": "迎战强降雨！紧急转移群众保安全",
        "source_org": "湖南省应急管理厅",
        "source_url": "https://yjt.hunan.gov.cn/yjt/tszt/ywzl/fxkz/202506/t20250620_33718940.html",
        "source_date": "2025-06-20",
        "created_at": "2025-06-19T05:50:00",
        "resolved_at": "2025-06-19T06:45:00",
        "workflow_steps": [
            "桑植县遭遇强降雨并提升防汛应急响应。",
            "乡镇督导村级开展隐患巡查排查。",
            "村干部发现浑浊泥土和滑坡风险后，叫醒住户并从二楼屋后转移1户3人。",
            "滑坡发生后确认无人员伤亡，向乡党委政府报告并纳入后续安置巡查。",
        ],
    },
    {
        "type": "landslide",
        "description": "2024年6月19日晚强降雨中，桑植县上洞街乡院子村张家湾组大庄滑坡出现变形迹象，受威胁群众已转移避险安置。",
        "lat": 29.5827,
        "lng": 110.1824,
        "district": "桑植县",
        "community": "院子村张家湾组",
        "scenic_area": "上洞街乡院子村",
        "severity": "high",
        "status": "responding",
        "reporter_role": "community_admin",
        "nearest_shelter_id": "zjj-safe-sz-yuanzicun",
        "source_title": "张家界破解山区防灾救援难题",
        "source_org": "湖南省人民政府门户网站",
        "source_url": "https://hunan.gov.cn/topic/fx2024/hnxd24/202406/t20240620_33335462.html",
        "source_date": "2024-06-20",
        "created_at": "2024-06-19T21:30:00",
        "resolved_at": None,
        "workflow_steps": [
            "地质灾害隐患点巡查员在强降雨中开展巡逻、排查和监控。",
            "发现大庄滑坡有变形迹象后，先行转移受威胁群众。",
            "安置点核对人员台账，乡村两级持续监测滑坡体变化。",
            "待雨情稳定和专业复核后，再决定解除管控或扩大避险范围。",
        ],
    },
    {
        "type": "landslide",
        "description": "2024年6月19日晚，永定区罗水乡大明村向家组滑坡隐患点经巡查显示目前正常，纳入强降雨期间滚动巡查复核。",
        "lat": 29.2105,
        "lng": 110.3568,
        "district": "永定区",
        "community": "大明村向家组",
        "scenic_area": "罗水乡大明村",
        "severity": "low",
        "status": "pending",
        "reporter_role": "community_admin",
        "nearest_shelter_id": "zjj-safe-tianmenshan",
        "source_title": "张家界破解山区防灾救援难题",
        "source_org": "湖南省人民政府门户网站",
        "source_url": "https://hunan.gov.cn/topic/fx2024/hnxd24/202406/t20240620_33335462.html",
        "source_date": "2024-06-20",
        "created_at": "2024-06-19T21:10:00",
        "resolved_at": None,
        "workflow_steps": [
            "强降雨期间按地灾隐患点责任体系启动巡查。",
            "巡查员反馈滑坡隐患点目前正常，登记为待复核事件。",
            "系统保留定位、责任区和最近安置点，便于后续叫应。",
            "下一轮降雨或现场变化时重新研判是否升级处置。",
        ],
    },
]


def seed_users() -> None:
    demo_users = [
        ("city_demo", "city_admin", None, None),
        ("county_admin_demo", "county_admin", "武陵源区", None),
        ("community_admin_demo", "community_admin", "武陵源区", "标志门社区"),
        ("resident_demo", "resident", "武陵源区", None),
        ("tourist_demo", "tourist", None, None),
    ]
    with session_scope() as db:
        for username, role, district, community in demo_users:
            user = db.scalar(select(UserDB).where(UserDB.username == username))
            if user:
                user.role = role
                user.district = district
                user.community = community
                continue
            salt = secrets.token_hex(8)
            db.add(
                UserDB(
                    username=username,
                    role=role,
                    district=district,
                    community=community,
                    salt=salt,
                    password_hash=_hash_password("123456", salt),
                )
            )


def seed_shelters() -> None:
    shelters = read_json(SHELTERS_FILE, [])
    with session_scope() as db:
        for item in shelters:
            record = db.get(ShelterDB, item["id"])
            if record:
                for key, value in item.items():
                    setattr(record, key, value)
            else:
                db.add(ShelterDB(**item))


def seed_alerts() -> None:
    alerts = read_json(ALERTS_FILE, [])
    with session_scope() as db:
        for item in alerts:
            record = db.get(AlertDB, item.get("id")) if item.get("id") else None
            payload = {
                "title": item["title"],
                "disaster_type": item.get("disaster_type", "暴雨/山洪/滑坡"),
                "level": item.get("level", "橙色"),
                "affected_areas": json.dumps(item.get("affected_areas", []), ensure_ascii=False),
                "started_at": item.get("started_at", ""),
                "duration": item.get("duration", ""),
                "advice": item.get("advice", ""),
                "status": item.get("status", "active"),
                "data_source_note": item.get("data_source_note", ""),
                "audience_messages": json.dumps(item.get("audience_messages", {}), ensure_ascii=False),
                "created_at": item.get("created_at") or now_iso(),
                "is_pushed": item.get("is_pushed", False),
                "pushed_at": item.get("pushed_at"),
                "district": item.get("district"),
                "community": item.get("community"),
            }
            if record:
                for key, value in payload.items():
                    setattr(record, key, value)
            else:
                db.add(AlertDB(id=item.get("id"), **payload))


def _shelter_payload(shelter: ShelterDB | None) -> str | None:
    if not shelter:
        return None
    return json.dumps(
        {
            "id": shelter.id,
            "name": shelter.name,
            "area": shelter.area,
            "lat": shelter.lat,
            "lng": shelter.lng,
            "capacity": shelter.capacity,
            "distance_km": 0.5,
        },
        ensure_ascii=False,
    )


def _incident_seed_items() -> list[dict]:
    file_items = read_json(INCIDENTS_FILE, [])
    return file_items if file_items else OFFICIAL_INCIDENTS


def _nearest_shelter_payload(db, item: dict) -> str | None:
    existing = item.get("nearest_shelter")
    if existing:
        return json.dumps(existing, ensure_ascii=False) if isinstance(existing, dict) else existing

    shelter_id = item.get("nearest_shelter_id")
    if not shelter_id:
        return None
    shelter = db.get(ShelterDB, shelter_id)
    return _shelter_payload(shelter)


def seed_incidents(replace_existing: bool = False) -> None:
    seed_items = _incident_seed_items()
    with session_scope() as db:
        if replace_existing:
            db.execute(delete(IncidentDB))

        for item in seed_items:
            payload = {
                "type": item["type"],
                "description": item["description"],
                "lat": item["lat"],
                "lng": item["lng"],
                "district": item["district"],
                "community": item.get("community"),
                "scenic_area": item.get("scenic_area"),
                "severity": item["severity"],
                "status": item["status"],
                "reporter_role": item.get("reporter_role", "community_admin"),
                "reporter_id": item.get("reporter_id", 1),
                "nearest_shelter": _nearest_shelter_payload(db, item),
                "source_title": item.get("source_title", ""),
                "source_org": item.get("source_org", ""),
                "source_url": item.get("source_url", ""),
                "source_date": item.get("source_date", ""),
                "workflow_steps": json.dumps(item.get("workflow_steps", []), ensure_ascii=False),
                "need_review": False,
                "is_demo": item.get("is_demo", True),
                "created_at": item["created_at"],
                "resolved_at": item.get("resolved_at"),
            }
            if replace_existing:
                db.add(IncidentDB(**payload))
                continue
            record = db.scalar(select(IncidentDB).where(IncidentDB.description == item["description"]))
            if record:
                for key, value in payload.items():
                    setattr(record, key, value)
            else:
                db.add(IncidentDB(**payload))


def seed_public_suggestions() -> None:
    with session_scope() as db:
        for item in PUBLIC_SUGGESTION_DEMO_DATA:
            existing = db.scalar(
                select(MessageDB).where(
                    MessageDB.source_type == "public_suggestion",
                    MessageDB.title == item["title"],
                    MessageDB.sender_id == item["sender_id"],
                )
            )
            payload = {
                "title": item["title"],
                "content": item["content"],
                "target_roles": json.dumps(["city_admin", "county_admin"], ensure_ascii=False),
                "target_district": item["target_district"],
                "target_community": item["target_community"],
                "target_user_id": None,
                "sender_id": item["sender_id"],
                "sender_role": item["sender_role"],
                "priority": "normal",
                "source_type": "public_suggestion",
                "related_id": None,
                "parent_id": None,
                "status": item["status"],
                "reply_content": item.get("reply_content", ""),
                "review_note": item.get("review_note", ""),
                "reviewed_by": item.get("reviewed_by"),
                "reviewed_at": item.get("reviewed_at"),
                "attachments": "[]",
                "created_at": item["created_at"],
            }
            if existing:
                for key, value in payload.items():
                    setattr(existing, key, value)
                suggestion = existing
            else:
                suggestion = MessageDB(**payload)
                db.add(suggestion)
                db.flush()

            if item.get("reply_content"):
                reply_title = f"建议反馈：{item['title']}"
                reply = db.scalar(
                    select(MessageDB).where(
                        MessageDB.source_type == "suggestion_reply",
                        MessageDB.parent_id == suggestion.id,
                    )
                )
                reply_payload = {
                    "title": reply_title,
                    "content": item["reply_content"],
                    "target_roles": json.dumps([item["sender_role"]], ensure_ascii=False),
                    "target_district": item["target_district"],
                    "target_community": item["target_community"],
                    "target_user_id": item["sender_id"],
                    "sender_id": item.get("reviewed_by") or 1,
                    "sender_role": "city_admin",
                    "priority": "city",
                    "source_type": "suggestion_reply",
                    "related_id": None,
                    "parent_id": suggestion.id,
                    "status": "sent",
                    "reply_content": "",
                    "review_note": "",
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "attachments": "[]",
                    "created_at": item.get("reviewed_at") or item["created_at"],
                }
                if reply:
                    for key, value in reply_payload.items():
                        setattr(reply, key, value)
                else:
                    db.add(MessageDB(**reply_payload))

            if item["status"] == "forwarded":
                task_title = f"调查整改：{item['title']}"
                task = db.scalar(
                    select(MessageDB).where(
                        MessageDB.source_type == "rectification_task",
                        MessageDB.parent_id == suggestion.id,
                    )
                )
                task_payload = {
                    "title": task_title,
                    "content": f"请核查群众反馈事项并形成整改结果。\n\n原始建议：{item['content']}",
                    "target_roles": json.dumps(["county_admin", "community_admin"], ensure_ascii=False),
                    "target_district": item["target_district"],
                    "target_community": item["target_community"],
                    "target_user_id": None,
                    "sender_id": item.get("reviewed_by") or 1,
                    "sender_role": "city_admin",
                    "priority": "city",
                    "source_type": "rectification_task",
                    "related_id": None,
                    "parent_id": suggestion.id,
                    "status": "sent",
                    "reply_content": "",
                    "review_note": "",
                    "reviewed_by": None,
                    "reviewed_at": None,
                    "attachments": "[]",
                    "created_at": item.get("reviewed_at") or item["created_at"],
                }
                if task:
                    for key, value in task_payload.items():
                        setattr(task, key, value)
                else:
                    db.add(MessageDB(**task_payload))
