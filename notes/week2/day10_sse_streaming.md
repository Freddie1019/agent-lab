# Day 10 概念卡片：SSE 流式输出

---

## 卡片 1：SSE vs WebSocket vs 轮询 🤖

LLM Agent 时代 SSE 胜出的根本原因：

| 维度 | SSE | WebSocket |
|------|-----|-----------|
| 协议 | HTTP | 独立协议 |
| 方向 | 单向（服务端→客户端） | 双向 |
| 中间件兼容 | ✅ 完美 | ❌ 经常被代理掐断 |
| 自动重连 | ✅ 浏览器原生 | ❌ 自己实现 |
| 复杂度 | ⭐ | ⭐⭐⭐ |

**Agent 通信本质单向** → WebSocket 的双向能力是浪费 → SSE 是天然最优解。

OpenAI / Anthropic / Google Gemini 全部用 SSE。

---

## 卡片 2：SSE 协议本身 🤖

SSE 不是新协议，是**普通 HTTP 响应 + 特殊 Content-Type + 特殊格式**。

响应头：`Content-Type: text/event-stream`

响应体：event: thought

data: 我开始思考...
event: tool_call

data: {"name": "web_search", "args": {...}}
event: done

data: [DONE]

关键约定：
- 每个事件以**空行**结束（`\n\n`）
- `:` 开头的行是注释（可用作心跳）
- 心跳必要：很多代理会主动关闭 N 秒不活跃的连接

---

## 卡片 3：Async Generator 🤖

让 FastAPI 流式输出必须用 async generator：

```python
async def event_generator():
    for event in agent.stream():
        yield format_sse(event)
        # 等待 LLM 时不阻塞其他请求

return StreamingResponse(event_generator(), media_type="text/event-stream")
```

**为什么必须 async**：
- LLM 调用是 I/O 操作（等网络）
- 同步 generator 会阻塞整个服务
- async generator 在等待时让出 CPU

这是 Week 4 异步编程的预热。

---

## 卡片 4：客户端断连处理 🤖

SSE 最大的工程坑：用户关浏览器了，服务端还在烧 token。

解决方案：FastAPI 的 `Request.is_disconnected()`

```python
async def event_generator():
    for event in agent.stream():
        if await request.is_disconnected():
            break  # 提前退出
        yield format_sse(event)
```

**没有这个检测，单次断连可能损失 $0.50-$5**。规模化后是真实的运营成本。

业界标准：检测断连 + 清理任务 + 保留已完成的工作（避免下次重做）。

---

## 卡片 5：流式破坏了 Day 9 的什么 ✍️

Day 9 你设计了 `ResearchResponse` Pydantic 模型 + RFC 7807 错误格式。这些在流式接口里基本失效。请回答：

- Day 9 的"统一响应模型"在流式接口里为什么用不了？
- 传统响应模型假设数据是一次性整体交付的，Pydantic可以在数据出库前做一轮完整的Schema校验。而流式输出的本质是碎片化的（Chunked），数据
- 像沙漏一样一点点漏给前端。所以在流的过程中，无法对一个“只吐了一半的JSON字符串”进行Pydantic校验，传统的Content-Length响应头也无法计算
- Day 9 的"统一错误格式（RFC 7807）"在流式里要怎么传？（流到一半挂了怎么办？）
- 在 SSE 的事件设计中，将错误升格为一等公民时间（Error Event）当流到一半系统崩溃时，生成器捕获到异常，立刻推送一个evnet：error其 data 
- 内部包裹符合 RFC 7807 规范的 JSON 字符串，随后主动关闭连接（yield 结束）。前端通过监听 addEventListener('error', ...) 或解析事件类型来捕获这个中途坠毁的错误。
- 流式接口怎么做 OpenAPI 文档化？
- FastAPI 无法直接自动把 StreamingResponse 转换成精确的流式字段文档。需要使用 responses 参数进行手动声明补全

---

## 卡片 6：事件类型设计哲学 ✍️

你今天定义了 8 种事件类型（agent_start / step_start / thought / tool_call / tool_result / answer_complete / agent_complete / error）。请回答：

- 这套事件类型对应了 Agent 工作的哪些"关键时刻"？
- 这套事件类型对应了Agent工作中的，初始对话循环、LLM的思考时刻、LLM工具调用时刻、工具执行结果、完成状态、错误等

- 如果让你简化到 3 种事件类型，你会保留哪 3 种？为什么？
- 如果必须精简，我会保留：
- thought（思维流）：向用户展示 Agent “正在想什么”，对抗白屏焦虑。
- tool_call（行动流）：让用户知道 Agent “正在干什么”（如调了什么工具、查了什么网页），建立可信度。
- answer（结果流）：最终输出的文本碎片的拼接。

- 如果让你扩展到 15 种事件类型，你还会加什么？（提示：参考 OpenAI Assistants API）
- 状态留痕类：thread_run_created / thread_run_queued（用于长任务排队状态提示）。
- 审批交互类：requires_action（Day 6 的 HITL 触发事件，流式暂停，等待用户点击）、action_submitted（用户批准后流式恢复）。
- 结构化附件类：file_generated（Agent 在后台画好了图表或生成了 PDF 报告）、suggested_replies（根据当前对话自动生成的快捷下一步追问按钮）。

---

## 卡片 7：客户端断连的成本经济学 ✍️

请基于今天的实战思考：

- 假设你有 1000 个用户在用 Agent，每人提交后 30 秒内有 20% 概率关闭页面。**没有断连检测**的情况下，每天会浪费多少 token？换算成钱大概多少？
- 假设 1000 个用户，每天每人提交 10 次请求，共 10000 次。20% 的用户中途关闭页面（2000 次）。没有断连检测时，Agent 会在后台把剩下的步骤跑完（假设平均多跑 30 秒，包含 3 轮大模型调用，
- 多烧 4000 OutputTokens）。每天浪费的 Token：$2000 \times 4000 = 8,000,000$ Tokens。换算成钱（以商业大模型主力模型价格预估）：每天大约损失 几十到上百美金。一年下来就是数万美金的纯粹财务黑洞！

- 断连检测之外，还有什么场景会导致"服务端继续烧 token 但客户端拿不到"？
- 移动端物理切网：用户从 Wi-Fi 走到电梯里切换为 5G，中间有十几秒的“网络盲区”，TCP 连接在网络层可能已经断开（或挂起），但服务端的 Web 服务器还没有感知到（直到 Keep-Alive 超时）。
- 浏览器标签页休眠（Tab Dormancy）：手机锁屏、或者将浏览器切到后台。现代操作系统（iOS/Android/Chrome）为了省电，会立刻冻结后台网页的 JavaScript 线程，导致接收缓冲区塞满，客户
- 端不再读取数据，但服务端的 Agent 依然在疯狂并发调用大模型。

- 提示：浏览器睡眠、手机锁屏、Wi-Fi 切换、移动网络丢包...

---

## 卡片 8：今天最关键的工程认知 ✍️

请用 2-3 句话总结：
- 从"请求-响应"模式切换到"事件流"模式，认知上最大的转变是什么？
- 认知上最大的转变：
- 从“完美封箱、一次交付”的死板 CRUD 思维，切换到了“生命周期连续体（Continuous Lifecycle）”的流式思维。写长寿命 Agent 的后端，本质上是在写一个状态广播台，
- 你必须时刻拉响喇叭，把 Agent 的每一个呼吸（思考、- 调用、纠错）以极低的延迟向全世界（前端）广播。

- 哪个工程概念你以前模糊（SSE / async generator / 断连检测 / 事件设计），今天清晰了？
- 最清晰的概念：
- 以前觉得流式输出是大模型天生自带的魔法，今天理清了：那是底层 Async Generator（异步生成器）在不断出让 CPU 时间片、以及 HTTP 协议里 text/event-stream 通过一个个 \n\n 空行切分事件所构建出来的工程管道。

---

## 还不明白的地方
（列出来下次问我）