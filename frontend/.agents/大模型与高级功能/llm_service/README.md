# 网络舆情事件智能分析系统：大模型与高级功能

## 1. 实现方案

模块采用 Flask Blueprint 封装，不依赖数据库，直接接收成员 A 的事件详情 JSON：

- `llm_service.py`：事件智能问答、无关问题拦截、API 故障降级。
- `trend_predictor.py`：纯 Python 一元线性回归，预测未来 24 小时。
- `report_generator.py`：真实大模型或 mock 模板生成 Markdown 报告。
- `llm_client.py`：调用 OpenAI 兼容的 `/chat/completions` 接口。
- `prompts.py`：问答和报告提示词。
- `api.py`：三个 Flask API 的 Blueprint。
- `app.py`：独立演示服务。
- `test_llm_service.py`：核心函数和 API 自动化测试。

真实 API 失败时会自动降级为规则问答/模板报告，保证演示不中断。输入上下文只保留事件白名单字段并限制长度；提示词要求模型拒绝无关问题、不得编造。

## 2. 安装与启动

```powershell
cd "C:\Users\fuzhixin\Desktop\网安实践"
python -m pip install -r llm_service/requirements.txt
$env:LLM_MOCK = "true"
python -m llm_service.app
```

服务地址为 `http://localhost:5001`，健康检查为 `GET /health`。

接真实通义千问兼容 API：

```powershell
$env:LLM_API_KEY = "你的密钥"
$env:LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:LLM_MODEL = "qwen-plus"
$env:LLM_MOCK = "false"
python -m llm_service.app
```

不要把 API Key 写进源码或提交到 Git。

## 3. 集成成员 A 的 Flask 后端

```python
from flask import Flask
from llm_service import create_llm_blueprint

app = Flask(__name__)
app.json.ensure_ascii = False
app.register_blueprint(create_llm_blueprint())
```

若主项目把 `llm_service` 目录放在 `backend` 下，上述代码保持不变。

## 4. 数据约定

事件对象推荐字段：

```json
{
  "id": 1,
  "title": "事件标题",
  "summary": "事件摘要",
  "keywords": ["关键词1", "关键词2"],
  "sentiment_distribution": {"positive": 20, "neutral": 30, "negative": 50},
  "trend_data": [{"time": "2026-07-09T10:00:00+08:00", "value": 120}],
  "platform_distribution": {"微博": 60, "抖音": 40}
}
```

兼容别名：`event_title`、`event_summary`、`sentiment`、`heat_trend`、`platforms`。情感和平台数值既可用百分数，也可用 0～1 比例。

## 5. API 示例

### POST `/api/llm/ask`

请求：

```json
{
  "event_data": {
    "title": "某品牌产品质量争议",
    "summary": "消费者发布质量问题视频，品牌方启动调查。",
    "keywords": ["产品质量", "品牌回应"],
    "sentiment_distribution": {"positive": 15, "neutral": 30, "negative": 55},
    "platform_distribution": {"微博": 55, "抖音": 30, "新闻": 15}
  },
  "question": "该事件当前主要风险是什么？"
}
```

响应：

```json
{
  "success": true,
  "answer": "当前可从热度变化和负面情感占比研判某品牌产品质量争议的风险；现有演示数据有限，建议结合最新趋势与异常增长点复核。",
  "mode": "mock",
  "model": "mock-rule-based"
}
```

### POST `/api/llm/predict`

请求：

```json
{
  "trend_data": [
    {"time": "2026-07-09T08:00:00+08:00", "value": 120},
    {"time": "2026-07-09T09:00:00+08:00", "value": 145},
    {"time": "2026-07-09T10:00:00+08:00", "value": 180}
  ]
}
```

响应（`predictions` 实际包含未来 24 个小时点）：

```json
{
  "success": true,
  "method": "linear_regression",
  "trend": "上升",
  "change_ratio": 3.9907,
  "interval_hours": 1.0,
  "predictions": [
    {"time": "2026-07-09T11:00:00+08:00", "value": 208.33}
  ]
}
```

### POST `/api/llm/report`

请求：

```json
{
  "event_data": {
    "title": "某品牌产品质量争议",
    "summary": "消费者发布质量问题视频，品牌方启动调查。",
    "keywords": ["产品质量", "品牌回应"],
    "sentiment_distribution": {"positive": 15, "neutral": 30, "negative": 55},
    "trend_data": [
      {"time": "2026-07-09T08:00:00+08:00", "value": 120},
      {"time": "2026-07-09T09:00:00+08:00", "value": 145}
    ],
    "platform_distribution": {"微博": 55, "抖音": 30}
  }
}
```

响应：

```json
{
  "success": true,
  "report": "# 某品牌产品质量争议舆情分析报告\n\n## 一、事件概述\n...",
  "format": "markdown",
  "mode": "mock",
  "model": "mock-template"
}
```

`mode` 可能为 `api`、`mock`、`fallback` 或 `guard`，前端通常只需展示 `answer` / `report`；若出现 `warning`，可仅记录到控制台。

## 6. 前端联调提示

- 问答页展示 `answer`，发送期间按钮 loading。
- 趋势预测把原数据与 `predictions` 作为 ECharts 两条折线，预测线建议用虚线。
- 报告可用 Markdown 渲染组件展示，或直接保留换行显示。
- HTTP 400 表示输入校验失败；HTTP 200 且 `mode=fallback` 表示真实 API 失败但已成功降级。

## 7. 功能测试指南

以下命令均在 `llm_service` 的上一级目录执行。例如当前目录结构为
`C:\Users\fuzhixin\Desktop\网安实践\llm_service`，则先执行：

```powershell
cd "C:\Users\fuzhixin\Desktop\网安实践"
python -m pip install -r llm_service/requirements.txt
```

### 7.1 自动化测试

使用 mock 模式运行全部核心函数和 Flask API 测试，不需要申请大模型 Key：

```powershell
$env:LLM_MOCK = "true"
python -m unittest llm_service.test_llm_service -v
```

正常情况下应显示 8 个测试全部为 `ok`，最后输出：

```text
Ran 8 tests
OK
```

测试覆盖：

- 智能问答 mock 返回；
- 无关问题拦截；
- 未来 24 小时趋势预测；
- 非法趋势数据校验；
- Markdown 报告生成；
- 三个 Flask API 的成功和失败响应。

### 7.2 启动本地测试服务

```powershell
$env:LLM_MOCK = "true"
python -m llm_service.app
```

服务默认监听 `http://localhost:5001`。另开一个 PowerShell 窗口测试健康检查：

复制命令时，只复制代码框内部的命令，不要复制开头和结尾的三个反引号，
也不要复制 `powershell` 字样。

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:5001/health"
```

预期返回：

```json
{"success": true, "service": "llm_service"}
```

### 7.3 测试智能问答

```powershell
$body = @{
  event_data = @{
    title = "某品牌产品质量争议"
    summary = "消费者发布产品质量问题视频，品牌方随后回应并启动调查。"
    keywords = @("产品质量", "品牌回应")
    sentiment_distribution = @{ positive = 15; neutral = 30; negative = 55 }
    platform_distribution = @{ "微博" = 55; "抖音" = 30; "新闻" = 15 }
  }
  question = "该事件当前主要风险是什么？"
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Method Post `
  -Uri "http://localhost:5001/api/llm/ask" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body
```

检查点：HTTP 状态为 200，`success=true`，并且 `answer` 非空。mock 模式下
`mode` 应为 `mock`；提问“帮我写一道数学题”时 `mode` 应为 `guard`。

### 7.4 测试趋势预测

```powershell
$body = @{
  trend_data = @(
    @{ time = "2026-07-09T08:00:00+08:00"; value = 120 },
    @{ time = "2026-07-09T09:00:00+08:00"; value = 145 },
    @{ time = "2026-07-09T10:00:00+08:00"; value = 180 }
  )
} | ConvertTo-Json -Depth 10

$result = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:5001/api/llm/predict" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body

$result
$result.predictions.Count
```

检查点：`success=true`、`trend=上升`，小时数据的 `predictions.Count` 为 24。
如果少于两个数据点，接口应返回 HTTP 400 和可读的 `error`。

### 7.5 测试报告生成

可复用 7.3 中的 `event_data`，补充 `trend_data`：

```powershell
$event = @{
  title = "某品牌产品质量争议"
  summary = "消费者发布产品质量问题视频，品牌方随后回应并启动调查。"
  keywords = @("产品质量", "品牌回应")
  sentiment_distribution = @{ positive = 15; neutral = 30; negative = 55 }
  trend_data = @(
    @{ time = "2026-07-09T08:00:00+08:00"; value = 120 },
    @{ time = "2026-07-09T09:00:00+08:00"; value = 145 }
  )
  platform_distribution = @{ "微博" = 55; "抖音" = 30 }
}
$body = @{ event_data = $event } | ConvertTo-Json -Depth 10

$result = Invoke-RestMethod -Method Post `
  -Uri "http://localhost:5001/api/llm/report" `
  -ContentType "application/json; charset=utf-8" `
  -Body $body

$result.report
```

检查点：`success=true`、`format=markdown`，报告包含“事件概述”“传播趋势分析”
“情感倾向分析”“风险等级研判”和“处置建议”五个部分。

### 7.6 测试真实大模型

```powershell
$env:LLM_API_KEY = "你的 API Key"
$env:LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:LLM_MODEL = "qwen-plus"
$env:LLM_MOCK = "false"
python -m llm_service.app
```

重新执行问答和报告请求。正常调用时 `mode=api`；网络或模型接口异常时，
服务仍返回 HTTP 200，并以 `mode=fallback` 提供降级结果，同时在 `warning`
中说明失败原因。这种设计用于保证课程演示不中断。

### 7.7 常见问题

- `No module named flask`：执行 `python -m pip install -r llm_service/requirements.txt`。
- `No module named llm_service`：确认当前目录是 `llm_service` 的上一级，而不是包目录内部。
- 端口被占用：修改 `app.py` 最后一行的 `port=5001`，并同步修改请求地址。
- 中文乱码：请求必须使用 `Content-Type: application/json; charset=utf-8`。
- 修改代码后仍显示旧结果：先按 `Ctrl+C` 停止服务，再重新运行
  `python -m llm_service.app`。
- 想强制演示 mock：设置 `$env:LLM_MOCK = "true"` 后重启服务。

前端开发请阅读 [FRONTEND_INTEGRATION.md](./FRONTEND_INTEGRATION.md)。
