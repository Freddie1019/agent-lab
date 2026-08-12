# Day21：状态一致性与数据库工程化

## 卡片1：Transaction

Transaction 把多个数据库操作组成一个原子业务单元。

全部成功才提交，否则全部回滚。

我的理解：
Transaction 是数据库保证数据一致性的“全有或全无（All-or-Nothing）”原子边界。
在 Agent 架构中，一个复杂的业务动作往往包含多表联动。例如：当接收到用户请求时，我们必须“创建 AgentRun”并“写入初始 RunStep”。如果这两个动作不包在同一个 Transaction 里，当 Step 写入失败时，数据库就会产生一个没有 Step 的孤儿 Run。事务（ACID）确保了这些操作要么全部生效，要么彻底撤销，绝对不留半完成状态的脏数据。

## 卡片2：Commit

Commit 正式结束当前事务并持久化修改。

我的理解：
Commit 是将事务内所有的修改持久化写进磁盘、并对其他并发连接正式可见的“终局确认”指令。
Commit 标志着一次原子操作的完美闭环。在异步 SQLAlchemy 中，执行 await session.commit() 会正式释放该事务持有的数据库行锁/表锁，并把内存中的修改写入磁盘物理日志。在 Agent 系统中，过早 Commit 会导致状态割裂，过晚 Commit 会长期占用连接池与锁资源，必须精准把握提交时机。

## 卡片3：Rollback

Rollback 撤销当前事务中尚未提交的修改。

我的理解：
Rollback 是在遭遇异常或校验失败时，将当前事务中所有未提交的修改彻底撤销、恢复如初的“时光倒流”机制。
这是 Agent 异常捕获（try...except）的核心防御工具。例如：在流式生成或工具调用中途抛出了未捕获的 Python 异常，此时 Session 内存里可能已经堆积了修改了一半的 ORM 对象。调用 await session.rollback() 可以瞬间清空当前的污染状态，保证数据库连接安全回归连接池，绝不让破损数据溜进数据库。

## 卡片4：Flush

Flush 会把待处理 SQL 发送到数据库，
但不会结束事务。

我的理解：
Flush 是将内存中的 SQL 变更指令推送到数据库 Server 端，但“保留事务窗口不关闭”的阶段性同步动作。
Flush $\neq$ Commit。 它的核心价值是获取数据库生成的自增 ID 或外键依赖，同时不结束事务。例如：我们要先创建 AgentRun（得到 run.id），再创建挂在它下面的 RunStep（需要 step.run_id）。通过 await session.flush()，数据库会立刻分配 run.id 给 Python 对象使用，但此时整体依然在同一个事务中，后续写 Step 失败依然可以整体 Rollback。

## 卡片5：Repository 的事务职责

Repository 负责数据访问。

业务 Service 决定多个 Repository 操作是否需要处于一个事务。

我的理解：
Repository 负责“数据的物理存取”，而 Service/Use-Case 层负责“业务事务边界的生命周期编排”。
这是领域驱动设计（DDD）的核心规则：Repository 内部绝对不能擅自调用 commit()。因为 Repository 只知道单个实体的读写，不知道上层业务的全貌。如果 AgentRunRepository 自己 commit 了，上层 Service 就再也无法把“写 Run”和“写 Step”打包成一个大事务。正确的做法是：Session/事务由 Service 层（或 FastAPI 依赖注入框架）统一控制，Repository 只负责在给定的 Session 内干活。

## 卡片6：Idempotency

同一个逻辑请求重复执行，不应该产生重复业务副作用。

我的理解：
幂等性是指：使用相同的参数对同一个接口发起一次或多次请求，外部物理世界产生的业务副作用（Side Effects）完全一致。
在网络抖动或前端狂点提交按钮时，客户端可能会短时间内重发 3 次一模一样的 HTTP 请求。如果不做幂等防护，后端就会启动 3 个并发的 AgentRun，白白浪费 3 倍的大模型 Token 资金，甚至触发 3 次重复扣款。具备幂等性的系统在收到重复请求时，会识别出“这事我已经干过了”，直接返回第一次的执行结果或状态。

## 卡片7：为什么需要数据库 UNIQUE？

应用层先查再写存在并发竞争。

数据库唯一约束才是最终一致性防线。

我的理解：
因为应用层的“先查后写（Check-Then-Write）”在并发面前形同虚设，数据库 UNIQUE 约束才是最终一致性的“物理铁闸”。
在代码里写 if not await repo.exists(key): await repo.create(...) 存在严重的并发竞态条件（Race Condition）。当两个完全相同的请求在同毫秒打进来时，它们会同时通过 exists 检查，随后同时执行 INSERT。唯有在数据库层面给 idempotency_key 加上 UNIQUE 索引，让第二次 INSERT 触发数据库底层的 IntegrityError，并在代码中捕获该异常，才能做到 100% 绝对的不重写。

## 卡片8：为什么不能用 Question 做幂等键？

Question 表示业务内容。

Idempotency-Key 表示一次客户端提交行为。

两者语义不同。

我的理解：
因为 Question 代表“业务内容”，而 Idempotency-Key 代表“客户端的一次特定提交动作”，两者语义完全错位。
用户在早上 9 点和下午 5 点分别问了一句一模一样的“今天天气怎么样？”，这是两次合法的独立业务意图，用户希望得到最新数据。如果把 Question 当作幂等键，第二次提问就会被系统误拦截，直接返回早上的旧答案。正确的幂等键必须是由前端/客户端生成的全局唯一 UUID（如 Header: X-Idempotency-Key），用来精准标识“这一次物理点击”。

## 卡片9：为什么不能保持长事务？

Agent 可能等待 LLM、网络和工具很长时间。

长事务会长期占用连接和数据库资源。

我的理解：
因为 Agent 调用 LLM 和网络工具极为耗时，长事务会迅速榨干数据库连接池并引发锁死。
大模型吐字或调第三方 API 可能会持续 10~30 秒。如果你在请求开始时 begin() 了一个数据库事务，并且在等待大模型响应的整个过程中一直不 commit，这会导致：占用一个 DB 连接长达 30 秒，高并发下连接池瞬间耗尽。事务持有的行锁无法释放，后续请求全部卡死（Lock Wait Timeout）。铁律：必须使用“短事务模式”——读数据库（短事务）$\rightarrow$ 关事务 $\rightarrow$ 调大模型/工具（无事务耗时）$\rightarrow$ 写数据库（短事务）。

## 卡片10：Alembic

Alembic 用 migration revision 管理数据库 Schema 演进。

我的理解：
Alembic 是 SQLAlchemy 生态下的数据库 Schema 版本控制与自动化迁移（Migration）工具。
在生产环境中，我们绝不能使用 Base.metadata.create_all()（因为它无法处理“修改现有字段”、“删除列”或“加索引”）。Alembic 就像数据库的 Git：每一次表结构修改（如 Day 21 给 agent_runs 表增加 idempotency_key 字段），都会生成一份版本化的 migration 脚本。它能安全、可追溯地在开发、测试和生产环境应用这些变更（Upgrade/Downgrade），且绝不破坏既有的物理数据。
