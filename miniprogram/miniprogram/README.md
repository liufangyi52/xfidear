# 智瞳应急平台小程序端

这是居民端和游客端的小程序实现，复用现有 FastAPI 后端能力：

- 首页：预警动态、最新下发消息、风险摘要
- 风险：微信 `map` 组件展示风险点和安置点提示
- 上报：现场上报、SOS（提交到后端，上级管理端可见）
- 消息：接收市级/区县级/社区端下发消息，提交信息建议
- 设置：查看身份、接口地址、实时连接状态

## 本地运行

1. 先启动项目后端：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -SkipInstall
```

2. 用微信开发者工具导入 `miniprogram` 目录。

3. 本地调试必须同时满足：
   - 微信开发者工具 → 详情 → 本地设置 → 勾选 **不校验合法域名、web-view、TLS 版本以及 HTTPS 证书**
   - `project.config.json` 与 `project.private.config.json` 中 `"urlCheck": false`
   - 修改配置后点击 **编译** 重新加载
   - 后端地址使用 `http://127.0.0.1:8000`，不要用 `localhost`

4. 演示账号：

```text
resident_demo / 123456
tourist_demo / 123456
```

## 接口地址

本地地址集中在 `utils/config.js`：

```js
module.exports = {
  apiBaseUrl: 'http://127.0.0.1:8000',
  wsBaseUrl: 'ws://127.0.0.1:8000'
}
```

部署到真实小程序时需要改成 HTTPS/WSS 域名，例如：

```js
module.exports = {
  apiBaseUrl: 'https://api.example.com',
  wsBaseUrl: 'wss://api.example.com'
}
```

## 实时接收

小程序登录成功后会连接：

```text
GET /api/ws/notifications?token=登录 token
```

当市级、区县级、社区端通过现有后台下发站内消息或推送预警时，后端会把新消息实时发送给在线小程序端；小程序收到后自动刷新“首页”和“消息”页面。断线后会自动重连，未在线时仍可通过 REST 收件箱拉取历史消息。
