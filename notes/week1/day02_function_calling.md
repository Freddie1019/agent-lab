# Day 2 概念卡片：Function Calling / Tool Use

---

## 卡片 1：Tool Use 的本质 🤖

**LLM 永远不执行任何代码**。"Tool Use" 是一个协议：
1. 你用 JSON Schema 告诉 LLM "我有哪些工具"
2. LLM 判断需要工具时，返回一个结构化的 JSON（"我想调 get_weather('Paris')"）
3. ★ **你的代码** ★ 解析这个 JSON，调用对应的 Python 函数
4. 你把函数结果作为新消息（role="tool"）送回 LLM
5. LLM 看到结果，生成自然语言回答

**关键认知**：LLM 是"指挥官"，你的代码是"士兵"。LLM 只下命令，从不动手。

---

## 卡片 2：工具描述（description）的重要性 🤖

LLM **只根据 `description` 判断该不该用、什么时候用、怎么用工具**。

- description 写得好 → LLM 选工具准确
- description 模糊 → LLM 会乱用、漏用、错用

实战建议：
- 第一句说"是什么"，第二句说"什么时候用"
- 参数的 description 要给例子
- 反例约束（"不要用于 XXX 情况"）也写在 description 里

> 这是为什么 prompt engineering 不只包括 system prompt，也包括 tool description。

---

## 卡片 3：messages 数组在 Tool Use 中的演化 🤖

一次完整的工具调用，messages 数组会变成：

```python
[
    {"role": "user", "content": "巴黎天气?"},
    {"role": "assistant", "content": None, "tool_calls": [...]},  # ← LLM 第一次回复
    {"role": "tool", "tool_call_id": "xxx", "content": "22°C"},   # ← 工具结果
    {"role": "assistant", "content": "巴黎 22 度晴朗"}              # ← LLM 第二次回复
]
```

新增了 `tool` 角色，承担"工具执行结果"的载体。

**关键约束**：
- `tool_call_id` 必须和上面 assistant 消息里的 id 对应
- tool 消息必须**紧跟在**有 tool_calls 的 assistant 消息之后
- 一次工具调用 = **两次** LLM 调用 + 一次函数执行

---

## 卡片 4：finish_reason 在 Agent 工程里的意义 🤖

`finish_reason` 的值是 Agent 工程的**核心状态机信号**：

| 值 | 含义 | Agent 该怎么做 |
|----|------|---------------|
| `stop` | LLM 觉得说完了 | 把答案返回给用户，循环结束 |
| `tool_calls` | LLM 想调工具 | 解析 tool_calls，执行工具，结果送回 LLM，**继续循环** |
| `length` | 被 max_tokens 截断 | 报警：要么放宽限制，要么压缩上下文 |
| `content_filter` | 触发安全审查 | 通常返回"我不能回答"或换个说法重试 |

**Day 3 你会基于 finish_reason 写出真正的 Agent 循环：当它是 `tool_calls` 就继续，是 `stop` 就退出。**

---

## 卡片 5：JSON Schema 在 AI 工程的地位 🤖

JSON Schema 是描述 JSON 数据结构的标准。**在 AI 工程里它无处不在**：

- **Tool 定义**：描述工具的参数（今天）
- **Structured Output**：强制 LLM 返回符合 schema 的 JSON
- **FastAPI 接口文档**：Day 1 的 /docs 背后就是 JSON Schema
- **Agent 状态机**：定义中间状态的结构

学好 JSON Schema 等于解锁了 AI 工程的通用语言。

---

## 卡片 6：tool_choice 参数的几种值 ✍️

请你查文档（OpenAI Function Calling 文档）补充：

- `tool_choice="auto"` 的含义：默认行为，模型会根据用户输入的上下文，自主决定是否需要调用工具，以及调用哪个或哪几个工具
- `tool_choice="none"` 的含义：禁用工具调用，显示的告诉模型，即便我们在 tools 参数中传入了工具列表，本次请求也绝对不允许调用任何工具。
- `tool_choice="required"` 的含义：强制工具调用（但不指定具体工具）。模型被强迫必须从你提供的工具列表中选择至少一个工具进行调用。
- `tool_choice={"type": "function", "function": {"name": "xxx"}}` 的含义：强制调用指定工具（特定工具锁定）。精确控制模型在本次交互中，必须且只能调用名为 "xxx" 的这一个特定函数。
- Agent 工程中，什么情况下不该用 "auto"？
- 虽然 "auto" 是默认且最省心的设置，但在构建严谨的生产级 Agent（如 ReAct 框架、多 Agent 协作系统、固定工作流）时，大量场景应该果断放弃 "auto"：
- 严格的确定性工作流
- 路由/分发 Agent（Router Agent）
---

## 卡片 7：并行工具调用的工程意义 ✍️

请你结合任务 5 的体验回答：

- 为什么现代 LLM 要支持"一次返回多个 tool_calls"？
- Token 成本与延迟爆炸：每一次工具调用都要把整个历史上下文重新发给模型，并发起一次新的网络请求。轮数越多，耗时越长，费用越高。
- 缺乏全局规划能力：现代 LLM 支持一次返回多个 tool_calls，意味着模型在理解用户意图的瞬间，就完成了任务的“并行拆解”。它能一次性把需要的信息全列出来，转交给后端并发执行，极大地提升了系统的吞吐量。
- 任务 5 里 3 个工具串行执行耗时多少？理论上并行能压到多少？
- 串行大于3s，并行能压到1s
- 实际工程中，什么场景下并行工具调用收益最大？（举 1-2 个 Agent 实战例子）
- 实战例子 1：AI 旅游/行程规划助手（信息聚合）
- 场景：用户说：“帮我看看下周五去西安的机票、兵马俑附近的酒店，顺便推荐两家高分肉夹馍店。”
- 并行表现：LLM 识别后，一次性返回 3 个 tool_calls：search_flights()、Google Hotels()、search_restaurants()。
- 收益：后端使用异步协程并发请求携程、美团等第三方接口。由于这三个查询互不干扰，原本需要 4-5 秒的等待，现在 1 秒出结果，用户体验极其丝滑。
---

## 卡片 8：今天最大的认知收获 ✍️

用 3 句话总结：今天对"什么是 Agent"的新理解。
（提示：和昨天单纯调 LLM 比，多了什么能力？少了什么限制？）
- Day2的LLM多了调用工具的能力
- LLM是能够“自主”决定该调用哪个工具，但执行工具是我们写的方法去进行的
- 框架概览
准备 tools schema → 调 LLM → 看 finish_reason
  → 是 tool_calls：解析参数 → 执行函数 → 结果塞回 messages → 再调 LLM
  → 是 stop：结束
框架做的事，就是把这个循环包装得更优雅、加更多功能（状态持久化、流式、错误重试、可观测性），但底层就是你Day2手写的这些东西。
---
