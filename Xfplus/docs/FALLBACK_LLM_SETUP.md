# 后备 LLM 配置说明

## 调用优先级

1. 讯飞星火：配置 `IFLYTEK_APPID`、`IFLYTEK_API_KEY`、`IFLYTEK_API_SECRET`。
2. 通义千问：配置 `DASHSCOPE_API_KEY`，并设置 `FALLBACK_LLM_TYPE=qwen`。
3. 本地 Mock：默认兜底模式，不需要任何 Key。

## 环境变量

```env
IFLYTEK_APPID=
IFLYTEK_API_KEY=
IFLYTEK_API_SECRET=
IFLYTEK_MODEL=generalv3
FALLBACK_LLM_TYPE=mock
DASHSCOPE_API_KEY=
AI_TIMEOUT_SECONDS=15
```

真实密钥只应写入本地 `.env` 或部署平台环境变量，不要提交到代码仓库。

## 前端表现

后端所有 AI 接口都会返回：

```json
{
  "fallback_used": true,
  "llm_provider": "mock"
}
```

当前端收到 `fallback_used=true` 时，会显示非阻塞提示：“当前 AI 使用备用模式，回答质量可能有波动”。

## Mock 覆盖范围

本地 Mock 覆盖一般避险问答、多角色预警文案、事件研判和 AI 复盘。因此即使公网环境中第三方模型不可用，演示流程也不会中断。
