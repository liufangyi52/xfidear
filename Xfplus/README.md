# 张家界·智瞳应急平台

## 项目概述

本项目以张家界市为落地场景，融合实时气象数据、地质灾害点信息与讯飞星火大模型，打造集预警发布、站内消息触达、现场上报、SOS 求助、指挥处置、AI 研判、语音播报和辅助复盘于一体的 AI+城市防灾应用。

系统定位为“比赛可上线运行版”：运行时数据写入 SQLite，站内消息形成真实触达闭环，居民/游客无后台权限，市级、区县级、社区/村部干部按层级管理本范围事件。短信、微信、真实广播等外部通道作为二期预留，本版本不替代政府正式应急系统。

## 技术架构

```text
Vue 3 + Vite 前端
  -> 五类角色入口、工作流菜单、预警动态、上报/SOS、风险地图、工作台、AI 悬浮助手、后台管理

FastAPI 后端
  -> 登录鉴权、预警、事件、消息、播报、AI、风险规则、天气与基础数据接口

SQLite 数据层
  -> users / alerts / incidents / messages / broadcast_records / shelters / notification_logs

外部能力
  -> 天地图 API、和风天气 API、讯飞星火、通义千问后备、本地 Mock、Web Speech API
```

## 技术栈

- 前端：Vue 3、Vite、Vue Router、Axios、Leaflet、leaflet.heat、天地图 API、Web Speech API。
- 后端：FastAPI、Pydantic、SQLAlchemy、SQLite、Uvicorn。
- AI：讯飞星火优先，通义千问可选后备，本地 Mock 兜底。
- 数据：SQLite 为主存储，JSON 作为种子数据和来源备份。
- 推送：v1 使用站内消息真实闭环，短信接口预留但不真实发送。

## 角色工作流

### 市级应急管理部门人员

默认进入 `/command/city` 工作台，菜单顺序为：工作台 → 预警发布 → 事件管理 → 消息管理 → 广播管理 → 复盘报告 → 风险数据 → AI 显隐切换。市级可查看全市态势、创建全市预警、向区县/社区/居民/游客下发消息，并触发一键演示事件。

### 区县级应急管理部门人员

默认进入 `/command/county` 工作台，菜单顺序为：工作台 → 预警发布 → 事件管理 → 消息管理 → 广播管理 → 复盘报告 → 风险数据 → AI 显隐切换。区县级仅能查看和处置绑定区县事件、创建本区县预警、向本区县目标人群下发消息。

### 社区/村部干部

默认进入 `/command/community` 工作台，菜单顺序为：工作台 → 预警转发 → 事件管理 → 消息管理 → 广播管理 → 复盘报告 → AI 显隐切换。社区/村部干部不能创建新预警，只能转发上级预警、处置本社区事件、向本社区居民/游客发送站内消息。

### 居民

默认进入 `/app` 预警动态页，底部 Tab 顺序为：首页 → 风险地图 → 上报/SOS → 我的消息 → 设置 → AI 显隐切换。居民可查看全市公开预警和风险点，只能看到本人区县内事件；提交事件时后端校验区县范围。

### 游客

默认进入 `/app` 预警动态页，底部 Tab 顺序为：首页 → 风险地图 → 上报/SOS → 我的消息 → 设置 → AI 显隐切换。游客可查看全市公开预警、风险点和匿名化事件；游客上报自动标记 `need_review=true`，SOS 仍作为高优先级事件进入指挥处置。

## 核心功能模块

### 1. 预警发布闭环

后台创建预警 → AI 生成多角色文案 → 保存 SQLite → 模拟推送 → 写入站内消息和播报记录 → 前台首页展示最新预警横幅。社区/村部干部只能转发上级预警到本社区。

### 2. 站内消息触达

管理角色可按权限向目标角色和辖区发送消息。居民和游客在首页横幅和“我的消息”中接收。事件处置完成后，系统会自动给上报人发送站内消息。

### 3. 现场上报 / SOS

居民和游客在 `/report` 提交现场事件或 SOS。前端支持提交中反馈、失败提示、离线草稿、恢复网络继续提交、定位失败后的手动坐标兜底。后端自动分类、定级、推荐最近安置点并进入工作台地图区域。

### 4. 指挥处置

市级看全市，区县级看本区县，社区级看本社区相关事件。工作台地图区域使用 Leaflet + 天地图 + 热力图，展示风险点、事件点和安置点；地图下方按工作流程提供预警、事件、消息、广播、复盘和风险数据等入口。

### 5. 风险地图

风险地图展示地质灾害隐患点、事件图层、热力图和安置点。点击风险点可查看风险等级、风险分值、建议行动、最近安置点和避险指引；点击事件点可查看状态、严重程度、上报角色和推荐安置点。

### 6. AI 悬浮助手

AI 助手不再占用独立菜单，升级为全局可拖拽悬浮头像“智瞳”。左键打开对话窗，右键或移动端长按可关闭，导航栏按钮可显隐切换。对话窗支持 Markdown、快捷问题、最近 5 条历史、`fallback_used` 提示，并调用通用接口 `POST /api/ai/chat`。

后端只向 AI 注入聚合统计信息，不注入未授权的具体事件详情；如需具体事件，用户应通过事件管理或我的消息中经过权限过滤的接口查看。

### 7. 语音播报与辅助复盘

语音播报使用 Web Speech API，移动端首次播放会提示点击“允许语音”完成激活。管理端可对预警和事件生成 AI 复盘报告，讯飞不可用时自动进入后备 LLM 或 Mock。

## 权限表

| 角色 | 可见后台 | 可创建预警 | 可下发消息 | 事件数据范围 |
|---|---|---|---|---|
| 市级应急管理部门人员 | 是 | 是（全市） | 是（全市） | 全市 |
| 区县级应急管理部门人员 | 是 | 是（本区县） | 是（本区县） | 本区县 |
| 社区/村部干部 | 是 | 否（可转发） | 是（本社区） | 本社区 |
| 居民 | 否 | 否 | 否 | 可见全市预警和风险点，仅可见本区县事件 |
| 游客 | 否 | 否 | 否 | 可见全市预警、风险点和匿名化事件，上报需审核 |

## 数据来源说明

- 天气数据：优先使用和风天气 API；无 Key 时使用模拟天气兜底。
- 地图底图：使用天地图 API（Tianditu），需配置 `VITE_TIANDITU_KEY`。
- 地质灾害点：`backend/data/disaster_points.json`，基于张家界市自然资源和规划局公开资料整理。
- 安置点：`backend/data/shelters.json`，根据景区公开地图、应急避险场所信息与比赛运行需求整理。
- 演示预警：`backend/data/demo_alerts.json`，基于历史暴雨预警和张家界山区景区风险场景改编。

更详细的数据来源见 [docs/DATA_SOURCES.md](docs/DATA_SOURCES.md)。

## API 接口

### 认证

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/me`

### AI

- `POST /api/ai/chat`：全局悬浮助手通用入口。
- `POST /api/ask`：兼容旧问答接口。
- `POST /api/generate_alert_text`
- `POST /api/generate_postmortem`

### 预警

- `GET /api/alerts`
- `GET /api/alerts/{id}`
- `POST /api/alerts`：市级、区县级。
- `PUT /api/alerts/{id}`：市级、区县级。
- `POST /api/alerts/{id}/push`
- `POST /api/alerts/{id}/forward`

### 事件

- `POST /api/incidents`
- `GET /api/incidents?status=&type=&time_range=24h|7d|all`
- `PUT /api/incidents/{id}/status`
- `POST /api/incidents/demo`
- `POST /api/incidents/analyze`

### 消息、指挥与基础数据

- `POST /api/messages`
- `GET /api/messages/inbox`
- `POST /api/notifications/test`
- `GET /api/command/overview?time_range=24h|7d|all`
- `GET /api/risk/current`
- `GET /api/risk-data`
- `GET /api/weather/current`
- `GET /api/disaster-points`
- `GET /api/shelters`
- `GET /api/broadcasts`

## 本地运行

### 1. 安装后端依赖

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

### 2. 初始化 SQLite

```powershell
python -m backend.scripts.init_db
```

默认数据库位置为 `backend/data/app.db`。部署时请确保 SQLite 文件所在目录可写并可持久化。

### 3. 启动后端

```powershell
uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

### 4. 启动前端

```powershell
cd frontend
npm install
npm run dev
```

### 5. 前端构建

```bash
cd frontend
npm run build
```

构建产物输出到 `frontend/dist/`。

## 演示账号

```text
city_demo / 123456
county_admin_demo / 123456
community_admin_demo / 123456
resident_demo / 123456
tourist_demo / 123456
```

## 环境变量

复制 `.env.example` 为 `.env`：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_TIANDITU_KEY=
FRONTEND_ORIGIN=http://localhost:5173
DATABASE_URL=sqlite:///D:/SpecialFolder/Documents/xfidear/backend/data/app.db
WEATHER_API_KEY=
QWEATHER_LOCATION_ID=101251101
IFLYTEK_APPID=
IFLYTEK_API_KEY=
IFLYTEK_API_SECRET=
IFLYTEK_MODEL=generalv3
FALLBACK_LLM_TYPE=mock
DASHSCOPE_API_KEY=
AI_TIMEOUT_SECONDS=15
```

真实 API Key 只写入 `.env` 或部署平台环境变量，不要提交到仓库。

## 部署说明

- 前端可部署到 Vercel/Netlify，设置 `VITE_API_BASE_URL` 为后端公网地址，设置 `VITE_TIANDITU_KEY` 为天地图 Key。
- 后端可部署到 Render/Railway/Python 服务平台，启动命令：

```bash
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

- SQLite 数据库必须放在平台的持久化磁盘路径，并设置 `DATABASE_URL`。
- 首次部署后执行 `python -m backend.scripts.init_db` 初始化表和演示账号。
- `FRONTEND_ORIGIN` 必须配置为前端公网域名，否则浏览器会出现 CORS 错误。

## 部署后测试清单

- 手机 iOS 微信 / Android Chrome 访问公网链接，检查首页无横向滚动。
- 配置 `VITE_TIANDITU_KEY` 后，风险地图和工作台地图区域可加载天地图瓦片。
- 首次点击“允许语音”后，再点击预警播放按钮，能听到中文播报或看到明确提示。
- 居民/游客无后台入口，直接访问 `/admin` 会回到 `/app`。
- 市级可查看全市 overview，区县级只能查看本区县，社区级只能查看本社区。
- 后台推送预警后，居民/游客首页出现站内消息或最新预警横幅。
- 游客提交 SOS 后，事件带 `need_review=true`，后台事件处置页可见。
- 事件状态改为“已完成”后，上报人收到站内消息。
- 无讯飞 Key 时 AI 使用 Mock 后备仍可运行；配置讯飞 Key 后可真实调用。

## 测试命令

```powershell
python -m compileall backend
python -m backend.scripts.init_db
cd frontend
npm run build
```
