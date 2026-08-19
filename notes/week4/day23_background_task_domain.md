# Day23：后台任务领域模型

## 1. 昨日遗留问题

Day22 解决了 Event Loop 阻塞，但 Agent 生命周期仍依赖 HTTP/SSE 连接。

我的理解：

HTTP/SSE 连接是“易失性”的网络信道。之前的 Agent 任务与 HTTP 请求同生共死，一旦网络波动、客户端刷新或浏览器断开，后台正在跑的 Agent 就会变成不可控的“孤儿任务”，甚至中断执行。真正的生产级 Agent 系统必须实现“网络连接”与“任务生命周期”解耦，把任务托管给数据库和后台 Worker。

## 2. TaskRecord

定义：描述任务调度生命周期的持久化领域对象。

当前作用：记录任务是否 queued、running、completed、failed 或 cancelled。

TaskRecord 是“业务与用户视角”的任务总账单。它关注的是这个任务从被创建、入队排队，到最终成功/失败的宏观调度状态。不论底层的 Agent 重试了多少次，用户只关心这个 task_id 对应的业务目标最终有没有完成。

TODO

## 3. AgentRun

定义：一次具体 Agent 执行的状态与轨迹载体。

当前作用：Worker 领取 Task 后创建；同一 Task 未来可以产生多个 AgentRun。

我的理解：

AgentRun 是“系统与物理视角”的一次真实执行尝试。它记录了 Agent 在某一次运行中的推理步骤轨迹、Tool 调用记录、Token 消耗量与异常 StackTrace。每次系统尝试运行 Agent，都会生成一个新的 AgentRun 实例，与 Task 形成明确的上下文隔离。

## 4. 202 Accepted

定义：服务器接受请求，但异步处理尚未完成。

当前作用：提交任务后快速返回 task_id，不等待 Agent 最终答案。

我的理解：

这是异步 RESTful API 的行业标准设计。 Fast API 接收到 Agent 提问后，不阻塞等待大模型思考，而是仅用 10ms 完成落盘并生成 queued 状态的 TaskRecord，随后立刻向客户端返回 202 Accepted 以及 task_id。前端拿到 task_id 后，可以通过轮询或长连接异步订阅进度。

## 5. Request Fingerprint

定义：对规范化请求内容计算的稳定摘要。

当前作用：区分相同请求重试与幂等键被不同请求错误复用。

我的理解：

这是防误用与防碰撞的“请求内容指纹（SHA-256 Hash）”。当用户携带 Idempotency-Key 提交请求时：

若 Key 存在且 request_hash 相同：判定为重复点击/网络重试，直接返回已创建的 task_id（实现绝对幂等）。

若 Key 存在但 request_hash 不同：判定为幂等键非法复用（用户改了 Prompt 却没换 Key），直接抛出 409 Conflict 阻止脏数据入库。

## 6. Task 与 Run 的一对多关系

定义：一个业务任务可以关联多次物理执行尝试。

当前作用：重试和恢复创建新 Run，同时保留旧 Run 历史。

我的理解：

这是“业务目标”与“物理执行”的完美解耦。一个 TaskRecord（Task）可以对应多个 AgentRun（Run）。如果 Run #1 因为网络超时失败了，Worker 可以安全地创建 Run #2 进行重试。这既保证了 Task 宏观状态的连续性，又完整保留了每一次物理执行的历史审计轨迹，不会出现旧日志被覆盖的问题。

## 7. 阻塞点与修复记录

| 问题 | Day23 处理 |
|---|---|
| HTTP 必须等待 Agent | 提交后只创建 queued Task |
| 客户端断线导致任务消失 | TaskRecord 持久化到数据库 |
| 重复点击创建重复任务 | 用户 + Idempotency-Key 唯一约束 |
| Key 被不同请求复用 | request_hash 检测并返回 409 |
| 用户横向读取任务 | 所有 Repository 查询包含 user_id |
| Task 与 Run 状态混淆 | 独立状态机，一对多关联 |

## 8. 成功证据

测试命令：

TODO

测试结果：

TODO

API 提交结果：

TODO

数据库 TaskRecord：

TODO

AgentRun 数量应为 0：

TODO

## 9. 当前限制

Day23 只接受和查询任务，还没有 Worker 领取任务。

没有实现 Redis、任务抢占、超时重试和取消竞争。

## 10. 明日问题

谁来领取 queued Task？

多个 Worker 如何避免重复领取？

Worker 崩溃后如何重新投递？