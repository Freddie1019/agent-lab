# Day20：Heartbeat 与 Stale Run

## 卡片 1：Heartbeat

Heartbeat 是运行中的任务定期写入的存活信号。

它用于判断负责执行 Run 的服务实例是否仍然存活。

我的理解：
心跳的核心逻辑是“以主动上报证明自己还活着”。当 Agent 进入 running 或 waiting_tool 状态后，后台的后台任务（Background Task）或事件循环会定期执行 UPDATE agent_runs SET last_heartbeat_at = NOW() WHERE id = :run_id。一旦超过预设的容忍阈值（例如 30 秒）没有收到更新，外部的监控程序就会判定该进程已“猝死”。

## 卡片 2：AgentEvent 和 Heartbeat

AgentEvent 描述业务执行进度。

Heartbeat 描述进程或运行任务是否仍然存活。

我的理解：
AgentEvent（业务层）：由大模型或工具触发（如吐出一个 Token、开启一个 Step），频率极其不固定（可能 1 秒吐 10 个 Event，也可能在调慢速 API 时 20 秒一个 Event 都没有）。它是发给前端 UI 看的。

Heartbeat（系统层）：按固定时间律动（Tick-tock），不管大模型有没有吐字、工具有没有返回，只要进程没死，心跳就会源源不断地刷入后台。它是发给对账控制面（Reconciler）看的。

## 卡片 3：Runtime Identity

Runtime Identity 是当前服务进程的唯一标识。

AgentRun 通过 runtime_id 记录由哪个实例负责执行。

我的理解：
在多节点部署（K8s 集群）下，当机器 A 领取并开始执行 Run_001 时，会将 AgentRun.runtime_id 标记为 node-A-uuid。这样设计的核心目的是“各司其职，防止抢占”：

机器 A 知道只有它自己有资格去更新 Run_001 的心跳。

当机器 A 崩溃时，其他机器可以通过 runtime_id == 'node-A-uuid' 快速定位并收割机器 A 留下的所有僵尸遗产，而不会误伤其他健康节点上跑的任务。

## 卡片 4：Stale Run

Stale Run 是数据库仍显示 running，
但 Heartbeat 已长期停止更新的 Run。

我的理解：
这就是典型的“名存实亡”。对于前端或用户来说，UI 会一直显示一个转不完的菊花；对于系统来说，占用的分布式锁或资源无法释放。Stale Run 是长任务 Agent 系统中必然出现的垃圾数据，必须通过自动化机制将其识别并强行拉回现实世界。

## 卡片 5：Reconciliation

Reconciliation 是比较数据库状态和实际运行状态，
并修复不一致数据的过程。

我的理解：
Reconciliation 是系统的清道夫进程。它会周期性地执行扫描：

期望状态：DB 显示 status = running。

实际状态：物理进程已经死亡，心跳断绝 60 秒。

修复动作（Reconcile）：强行将 DB 状态修改为 interrupted，写入 error_detail = "Runtime heartbeat timeout"，并触发中断恢复流程（Day 19）。

## 卡片 6：为什么启动时扫描？

旧服务崩溃后无法修复自身状态。

新服务启动时必须清理旧实例留下的活动状态。

我的理解：
当 Pod A 因为 OOM 或宿主机宕机直接崩溃时，Pod A 进程已经不复存在，它绝不可能在死后去执行 SQL 修正自己的状态。因此，当新的 Pod B 启动（或旧 Pod A 重启）时，第一件事就是扫描数据库：查找所有绑定了旧 runtime_id、或者所有心跳已经超时的 running 任务，将它们统一清洗为 interrupted。 这是服务自愈（Self-healing）的第一步。

## 卡片 7：为什么 waiting_user 不自动 Stale？

waiting_user 可能合法地长时间等待用户审批，
不能仅因为没有 Heartbeat 就中断。

我的理解：
因为 waiting_user 属于“带外人类异步响应（Human-in-the-Loop）”，它的阻塞是符合业务预期的正常停顿。
在 Day 6 的 HITL（人类干预）场景中，Agent 要执行敏感动作（如删库、发邮件），停下来等待人类审批。用户可能去吃了个午饭、或者下班第二天来才在前端点“允许”。在这个过程中，后台的 CPU 线程并没有在疯狂耗算力，心跳暂停是正常的。如果把 waiting_user 误判为 Stale Run 并强行终止，就会彻底破坏人机协同的完整性。

## 卡片 8：为什么 waiting_tool 风险更高？

工具可能已经执行，但结果没有写回。

自动重试可能重复产生副作用。

我的理解：
因为 waiting_tool 阶段处于“物理副作用悬而未决”的暗盒区，盲目清理或重试极易触发重大的生产事故。
当一个 Run 在 waiting_tool 状态下变成了 Stale：
网络可能切断了，但外部第三方系统可能已经把动作执行了（比如钱已经扣了，但回执没传回来）。
如果清道夫程序直接把这个 Run 划为 failed 并自动让 Day 19 去 Retry 重跑工具，就会发生二次扣款。因此，waiting_tool 变成 Stale 时，对账程序通常只能标记为 interrupted 并发出告警，绝对禁止盲目自动无感重试。

## 卡片 9：为什么 Heartbeat 使用独立 AsyncSession？

SQLAlchemy AsyncSession 不应该被多个并发任务共享。

我的理解：
为了防止心跳逻辑与主业务事务（Business Transaction）产生“锁竞争（Lock Contention）”和“事务污染”。
主业务逻辑（如 Agent 正在生成一段几千字的长文）可能在一个大事务里，或者被某个耗时操作阻塞了 AsyncSession。如果心跳也去挤同一个 AsyncSession：

心跳 UPDATE 可能会因为主事务未提交而卡死。

如果心跳 UPDATE 报错，可能会导致整个主业务事务被 SQLAlchemy 强制回滚（Rollback）。
心跳必须拥有自己独立的、即用即丢的数据库连接与 AsyncSession，做到了“业务归业务，脉搏归脉搏”。

## 卡片 10：Day19 和 Day20 的关系

Day20 把异常残留的 running Run 修复为 interrupted。

Day19 再负责对 interrupted Run 生成 RecoveryPlan。

我的理解：
Day 20 是“死因诊断与收尸（Problem Detection）”，Day 19 是“读档复活与重生（Problem Recovery）”；两者共同构成了完整的自愈闭环。
它们是完美接力棒的关系：

Plaintext
[物理崩溃发生了]
       │
       ▼
Day 20 (Reconciliation 扫描到心跳断绝)
       │  ──> 将僵尸 Run 的状态从 running 修正为 interrupted
       ▼
Day 19 (Recovery Pipeline 被激活)
       │  ──> 提取最近的 Checkpoint，创建子 Run
       ▼
[Agent 成功从 Step N 读档复活继续运行]
没有 Day 20，崩溃的任务会永远卡在 running，Day 19 的恢复代码就永远等不到执行的机会；没有 Day 19，Day 20 扫出来的僵尸任务就只能冰冷地死在数据库里。两者的结合，标志着你的 Agent 框架正式具备了企业级的“高可用与故障自愈（High Availability & Fault Tolerance）”能力！