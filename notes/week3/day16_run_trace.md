# Day16：RunStep 与 ToolCallRecord 设计

## 今日主题

让 Agent 的执行过程从“只有整体状态”升级为“可回放、可分析、可诊断的执行轨迹”。

---

## 卡片 1：为什么生产级 Agent 需要执行轨迹？

Agent 的结果不是一次计算出来的，而是经过多步推理、工具调用和观察得到的。

如果没有执行轨迹，就无法定位错误、分析性能、审计工具调用。

我的理解：

普通 API 报错，看一眼堆栈（Stack Trace）就能定位到是哪行代码崩了。但 Agent 是个黑盒回路系统：它在第 2 步由于 LLM 幻觉生成了错误的工具参数，导致第 3 步工具报错，最终在第 4 步给出了垃圾答案。如果没有完整的执行轨迹，你根本无法判定到底是“大模型理解歪了”、“工具代码写 Bug 了”还是“检索召回（RAG）了脏数据”。执行轨迹是模型调优、工具审计、以及还原现场的唯一依据。


---

## 卡片 2：AgentRun、RunStep、ToolCallRecord 的关系

AgentRun：一次整体执行。  
RunStep：执行过程中的一个步骤。  
ToolCallRecord：某一步里的工具调用记录。

我的理解：
AgentRun (一次整体长任务运行, 如 Run_001)
   │
   ├── RunStep (Step 1: 规划与搜索, 如 Step_101)
   │     └── ToolCallRecord (调用 GoogleSearch 接口, 耗时 1.2s)
   │
   └── RunStep (Step 2: 整理并生成回答, 如 Step_102)
         └── (无工具调用，纯 Text 渲染)

AgentRun：是顶层容器。它管的是“总体成败”（Queued $\rightarrow$ Running $\rightarrow$ Completed）。RunStep：是执行的“生命节拍”（Ticks）。Agent 每和 LLM 交互一次、或者执行一次动作，就代表一个 Step。它负责记录每个步骤的 Thought（内心独白）和产生的 Action 类型。ToolCallRecord：是 Step 里的“物理副反应”。一个 Step 可能会并发并行地调 3 个工具（比如同时查天气、查股价、查新闻），因此一个 Step 旗下可以挂载 0 到多个独立的 ToolCallRecord。


---

## 卡片 3：RunStep 解决什么问题？

RunStep 记录第几步发生了什么，包括 thought、tool_call、tool_result、answer、error。

我的理解：
它将长达数分钟的 AI 思考黑盒拆解成了一帧一帧的“动画切片”。每一个 Step 都是一个原子上下文（Turn），记录了这一步的：
thought（LLM 的推理逻辑）
tool_calls（发出的动作意图）
tool_results（物理世界的反馈）
error（本步骤是否发生局部容错或降级）
通过结构化记录 RunStep，前端不仅能实时展现“Agent 正在阅读网页...”这种细腻的动态，后端还能以此实现断点重试（即如果 Step 3 失败，不需要从 Step 1 重跑，直接带着 Step 1 & 2 的快照恢复运行）。

---

## 卡片 4：ToolCallRecord 解决什么问题？

ToolCallRecord 记录工具调用的参数、结果、耗时、成功失败、安全信息。

我的理解：
工具调用（Tool Call）是 Agent 真正改变物理世界、或消耗真实资金的危险动作。ToolCallRecord 就像是一张高精度的发票，它记录了：
调用的工具名（tool_name）与原始入参（arguments）——用于安全合规审计，防止越权或注入攻击。
耗时（duration）——定位性能瓶颈（如哪个第三方 API 拖慢了整体响应）。
返回码与原始回执——评估工具的可用性与错误率。

---

## 卡片 5：为什么不能只把工具调用写进日志？

日志主要给人临时排查。  
ToolCallRecord 是结构化数据，可以用于查询、统计、审计、成本分析。

我的理解：
如果只打 logger.info(f"Calling tool {name} with {args}")，当系统达到日活百万时，日志会堆积成汪洋大海。你根本无法写出 SQL 查出：“过去 24 小时里，DatabaseQueryTool 的平均耗时是多少？失败率是多少？有多少次因为输入了非法 SQL 触发了安全拦截？” 只有将其结构化落库为 ToolCallRecord，才能接入 APM（应用性能监控）系统，支持多维度的聚合统计、成本核算与自动化告警。

---

## 卡片 6：AgentEvent 和 RunTrace 的关系

AgentEvent 是流式推送给客户端的事件。  
RunTrace 是服务端保存的执行轨迹。  
同一个 event 可以同时用于前端展示和后端记录。

我的理解：
它们是同源数据在不同维度的表现形式。当大模型吐出一个 Step 的 Thought 时，后台不仅要立刻把这个 Thought 封装成 AgentEvent 并通过 SSE 推送给前端浏览器（保证极低的首字延迟）；同时，必须在后台异步地把这个 Thought 写入当前 RunStep 的内存实体中（保存轨迹）。Event 负责实时通信，Trace 负责持久审计。
---

## 卡片 7：为什么 tool_call 和 tool_result 最好有 tool_call_id？

并发工具调用时，仅靠 tool_name 很难准确匹配调用和结果。  
tool_call_id 可以唯一关联一次工具调用。

我的理解：
现代 LLM（如 GPT-4o、DeepSeek-V3）支持一次性吐出 3 个并行的工具调用（例如：同时查北京、上海、东京的天气）。如果后端用多线程或协程去并发请求这三个天气 API，由于网络波动，东京的数据可能比北京先返回。如果没有 tool_call_id 作为全局唯一锚点，后端根本无法将返回的“阴天，15度”精准匹配给“东京”，从而导致严重的数据张冠李戴（Race Condition）。

---

## 卡片 8：为什么 raw_event_data 要谨慎保存？

原始事件数据方便调试，但可能很长，也可能包含敏感信息。  
生产环境需要截断和脱敏。

我的理解：
直接把 LLM 返回的几万字原始 JSON 塞进 raw_event_data 存盘虽然省事，但会带来两大灾难：
存储雪崩：高并发下，冗余的 API 包体会迅速榨干数据库（尤其是 relational DB）的空间，导致存储成本飙升。
合规雷区：原始数据中极易包含用户临时输入的敏感信息（如密码、API Key、甚至是医疗隐私卡片 13 的内容）。如果未经脱敏（Data Masking）和限长截断就直接落库，一旦数据库被拖库，就会面临毁灭性的法律指控。

---

## 卡片 9：RunTrace 和 Day17 数据库的关系

Day16 先用内存版建模。  
Day17 会把 AgentRun、RunStep、ToolCallRecord 持久化到数据库。

我的理解：
我们先在内存里用 Python Class（如 RunStepStore）把“增删改查、树状关联匹配、并发锁”的纯业务逻辑写顺、把单元测试跑通。明天的 Day 17，我们只需要使用 SQLAlchemy 编写对应的数据库 Schema，并将内存 Store 的实现零摩擦替换成 PostgreSQL 或 MySQL 驱动。这种两步走战略，完美避开了“边调状态机边 Debug SQL 语句”的泥潭，是顶尖后端架构师的标配开发节奏。