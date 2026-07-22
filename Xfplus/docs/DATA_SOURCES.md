# 数据来源说明

## 运行数据

- v1 主存储为 SQLite，默认文件为 `backend/data/app.db`。
- `backend/data/*.json` 仅作为初始化种子和公开资料备份，不再作为运行时主存储。
- 首次部署或重建数据库时执行 `python -m backend.scripts.init_db`，系统会写入演示账号、预警和安置点基础数据。

## 天气数据

- 首选来源：和风天气免费 API。
- 配置方式：在 `.env` 中填写 `WEATHER_API_KEY`。
- 回退规则：未配置 Key、API 超时或返回错误时，后端返回基于历史强降雨场景的仿真数据，并在响应中标记 `simulated=true`。

## 地图底图

- 默认来源：天地图 API（Tianditu）。
- 配置方式：前端环境变量 `VITE_TIANDITU_KEY`。
- 申请入口：https://console.tianditu.gov.cn/
- 未配置 Key 时，地图页会显示提示，风险点和事件面板仍可查看；上线演示前必须配置有效 Key。

## 地质灾害点

- 种子文件：`backend/data/disaster_points.json`
- 来源说明：基于张家界市自然资源和规划局公开的地质灾害隐患点列表（2023 年）整理。
- 参考入口：https://zrzygh.zjj.gov.cn/
- v1 作为静态基础数据读取，后续可迁移到数据库并支持后台维护。

## 安置点

- 种子文件：`backend/data/shelters.json`
- 运行表：`shelters`
- 来源说明：根据张家界景区公开地图、应急避险场所信息与比赛上线运行需求整理。
- 首次初始化后写入 SQLite，前台首页和风险/指挥地图均从数据库读取。

## 预警与事件

- 预警种子：`backend/data/demo_alerts.json`
- 运行表：`alerts`
- 现场事件运行表：`incidents`
- 演示预警包含 `data_source_note`，用于说明历史案例或仿真场景来源。
- 一键演示事件会写入 SQLite，并标记 `is_demo=true`。

## 站内消息与通知

- 站内消息运行表：`messages`
- 播报记录运行表：`broadcast_records`
- 短信预留日志表：`notification_logs`
- v1 真实触达方式为站内消息；短信接口仅记录预留日志，不真实发送。
