# Day15：AgentRun 状态机设计

## 今日主题

把一次 Agent 执行过程建模成 AgentRun，让执行过程可追踪、可查询、可恢复。

---

## 卡片 1：为什么 Agent 系统需要 AgentRun？

普通聊天系统可能只需要 Session 和 Message。  
但 Agent 一次回答可能包含多步推理、工具调用、错误恢复和中断处理。

AgentRun 用来表示这一次执行过程。

我的理解：
在普通聊天（如早期的 ChatGPT）中，用户输入，LLM 吐出，是一个简单的单次 I/O。但在 AI Agent 时代，用户发一句话，Agent 可能要先“规划”，再“查谷歌”，再“写代码”，再“纠错”。这个过程可能长达几分钟。如果不把这次“执行过程”抽象为一个独立的实体（AgentRun），你就无法回答以下生产问题：当前 Agent 到底卡在哪个工具了？它已经烧了多少 Token？如果突然断线，后台哪个任务应该被杀掉？AgentRun 就是这个长任务的唯一生命周期载体。

---

## 卡片 2：Session、Message、AgentRun 的区别

Session：一段长期会话。  
Message：会话中的一条消息。  
AgentRun：Agent 为了回答某条用户消息而执行的一次运行过程。

我的理解：
Session（会话层 - 空间视角）：是用户看到的聊天窗口，承载的是“上下文跨度”和历史归档。
Message（数据层 - 最终产物）：是会话里的文本节点（User 说什么，Assistant 回什么），属于静态的“结果留痕”。
AgentRun（执行层 - 物理进程）：是隐藏在 Message 背后的动力引擎。用户发了一条 Message（Input），系统就会生成一个 AgentRun 去拼命干活，最终干完活后，再生成一条 Assistant Message（Output）挂在 Session 里。一个 Session 可以有很多 Message，而生成一条 Message 的背后可能经历了多次失败重试的 AgentRun。

---

## 卡片 3：为什么不能只用 Message.status？

Message.status 描述的是最终消息是否完整。  
AgentRun.status 描述的是执行过程当前处于什么状态。

我的理解：
如果只用 Message.status（如 PENDING / SUCCESS / FAILED），你只能告诉前端“这条消息还在加载”或者“这条消息失败了”。但这对于长任务 Agent 来说是一场灾难。用户看着一个转了 2 分钟的菊花，根本不知道 Agent 此时是正在深度思考、还是卡死在某个第三方 API 超时里。AgentRun 拥有更精细的业务状态（如 waiting_tool），它能清晰地剥离出“过程状态”与“结果状态”，让前端能够做精准的进度条渲染和逐步的用户引导。

---

## 卡片 4：状态机是什么？

状态机描述一个对象在不同状态之间按照规则流转。

例如：

```text
queued → running → completed
running → waiting_tool → running → completed
running → failed
running → interrupted

我的理解：
状态机最核心的价值是防并发冲突与逻辑越界。它不仅定义了对象有哪些状态，更死死限制了“谁能跳到谁”。例如：一个任务只有先处于 running，才能跳到 completed 或 failed。如果系统突然收到一个指令，试图把一个已经是 failed 的任务改成 running，状态机就会铁面无私地抛出 InvalidStateTransition 异常。这在复杂的并发 Agent 场景下，是防止状态被工具回调或前端乱点污染的终极铁闸。

```
## 卡片 5：AgentRunStatus

本项目 Day15 设计的状态包括：

queued
running
waiting_tool
waiting_user
completed
failed
interrupted
cancelled

我的理解：
queued：排队中。大并发下，由于你的大模型 Token 速率限制（RPM/TPM）满了，任务在队列里等待令牌。
running：大模型正在疯狂进行 Reason 推理或生成文本。
waiting_tool：Agent 发出了工具调用申请，后台网络（如 HttpClient）正在去请求第三方服务。
waiting_user：Day 6 的 HITL 落地状态。Agent 要删库或发邮件，停下来等待人类在前端点“允许”。
completed：大模型吐出了最终答案，完美收工。
failed：系统运行时崩溃（LLM 报 500、代码抛异常）。
interrupted：网络抖动、客户端主动断连、或者手机休眠导致的流式“中途坠毁”。
cancelled：用户看它想歪了，手动点击了 UI 上的“停止生成”按钮。

## 卡片 6：流前错误和 AgentRun 的关系

如果认证失败、session 不存在、锁冲突，流还没开始，通常不创建 AgentRun。

我的理解：
如 Day 14 所述，当发生 401 鉴权失败、422 参数错误或 409 会话锁冲突时，请求在路由依赖注入（Depends）阶段就被熔断了。这时候服务端的 Agent 大脑连眼睛都没睁开，根本没有开始产生物理上的“执行动作”。因此，坚决不创建 AgentRun 记录，防止数据库里充斥着大量的黑客恶意扫描或压测产生的无用垃圾状态日志。

## 卡片 7：流中错误和 AgentRun 的关系

如果 LLM 或工具在流中失败，AgentRun 应该进入 failed 状态，并记录 error_type 和 error_detail。

我的理解：
一旦进入流中（生成器已激活），AgentRun 状态必然是 running。如果此时底层抛出不可逆的异常，我们必须在 try...except 块中，冷酷地把 AgentRun 的状态强行推向 failed。同时，必须将 error_type（如 OpenAIAPIError）和 error_detail（堆栈快照）序列化存入该 Run 记录。这是生产环境中排查 AI 幻觉、工具崩溃的最核心审计线索（Audit Trail）。

## 卡片 8：客户端断开和 interrupted

客户端断开不一定是系统失败，但说明本次 run 没有完整结束，因此应该标记为 interrupted。

我的理解：
用户进电梯切网、或者直接关掉 Tab 页，这时候后端的 Agent 算力可能还在健康地跑着，工具也返回了正确结果，系统本身并没有错。所以如果记成 failed，运维监控会频繁误报系统故障。记为 interrupted 意味着这是网络层面的物理掐断，提示清道夫程序去杀掉后台幽灵流量，并为后续的“断点续传/恢复执行”留下明确的墓碑标记。

## 卡片 9：AgentEvent 和 AgentRun 的关系

AgentEvent 是发给客户端看的流式事件。
AgentRun 是服务端保存的执行状态。
可以通过 AgentEvent 更新 AgentRun 状态。

我的理解：
在代码实现上，Agent 内部的状态机在流转时（例如从推理切到调工具），会触发一个 transition_to(AgentRunStatus.waiting_tool)。状态机变更成功的瞬间，会顺手将这个变更包装成一个 AgentEvent(event="step_start", data=...) 通过 SSE 管道 yield 广播给前端。AgentRun 的物理落库是权威事实，AgentEvent 则是这个事实面向前端的流式投影。

## 卡片 10：为什么 Day15 先用内存版 RunStore？

因为今天重点是状态建模，而不是数据库实现。
Day17 会把 RunStore 迁移到数据库。

我的理解：
如果今天一边设计复杂的状态机流转逻辑，一边去写 SQL、调 SQLAlchemy 关系映射、搞数据库迁移，两线作战极易导致逻辑混乱。先用一个 Python 的内存字典（dict[str, AgentRun]）作为 mock 仓储，我们可以把状态机的流转规则、边界条件、异常捕获在纯内存中测得滴水不漏。等到领域模型完全稳定后，Day 17 只需要把底层仓储换成持久化 DB 驱动，上层状态机不需要改动一行代码，这就是高阶后端的模块化美学。