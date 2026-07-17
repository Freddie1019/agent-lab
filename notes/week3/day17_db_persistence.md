# Day17：数据库持久化设计

## 今日主题

把 Session、Message、AgentRun、RunStep、ToolCallRecord 从内存状态迁移到数据库持久化。

---

## 卡片 1：为什么生产级 Agent 必须持久化？

内存状态在服务重启后会丢失。  
生产系统需要长期保存会话、运行状态、执行轨迹、工具调用记录和错误详情。

我的理解：
在生产环境中，服务器随时可能因为滚动更新、OOM（内存溢出）或硬件故障而重启。如果数据都在内存里，用户的聊天历史和正在运行的 Agent 任务会全部瞬间蒸发。更重要的是，持久化不仅是为了“防丢失”，更是为了提供离线审计、用户账单结算（Token 计费）、以及大模型微调数据（SFT）的冷数据源。

---

## 卡片 2：ORM 是什么？

ORM 是对象关系映射，让 Python 对象可以映射到数据库表。

我的理解：
ORM 的核心价值是消除胶水代码。如果不用 ORM，你需要在 Python 里拼接大量的 INSERT INTO run_steps... 这种长字符串 SQL 语句，极易引发 SQL 注入且难以维护。通过 ORM，数据库里的每一行记录都被映射为一个干净的 Python 对象，你可以直接用 run.status = "completed" 来改写数据，ORM 会自动在底层帮你翻译成对应数据库的 SQL 语句。

---

## 卡片 3：Engine 是什么？

Engine 是 SQLAlchemy 连接数据库的入口。

我的理解：
Engine 扮演的是交通枢纽的角色。它不负责具体的业务查询，但它死死管着“如何与 PostgreSQL/MySQL 建立物理连接”、“网络连接断开后如何自动重连”，以及“如何把 SQLAlchemy 的通用指令翻译成特定数据库的特定方言”。在异步架构中，我们必须使用 create_async_engine() 来初始化它，确保数据库的网络 I/O 不会卡死 FastAPI 的主事件循环。

---

## 卡片 4：AsyncSession 是什么？

AsyncSession 是一次数据库操作上下文，用于查询、提交、回滚事务。

注意它和聊天 Session 不是一个概念。

我的理解：
⚠️ 概念隔离警告：此 Session 非彼 Session！ 业务上的“聊天 Session”代表的是人机对话的上下文；而数据库的 AsyncSession 代表的是一次数据库连接会话，是包揽了 begin()、commit()、rollback() 的事务框。

AsyncSession 是用来保证 ACID 事务特性的。例如在创建 AgentRun 的同时必须创建第一个 RunStep，这两个动作必须包裹在同一个 AsyncSession 事务中。如果写 Step 时网络崩了，Session 会自动触发 rollback() 回滚，确保数据库里不会留下只有 Run 没有 Step 的破坏性垃圾碎片。

---

## 卡片 5：为什么要区分 Pydantic Model 和 ORM Model？

Pydantic Model 面向业务逻辑和数据校验。  
ORM Model 面向数据库表结构和持久化。

我的理解：
Pydantic Model（数据校验层）：运行在内存中，负责在 HTTP API 的边缘检查前端传来的参数合不合法，或者把数据序列化成 JSON 返回给前端。它关注的是输入输出的形态与校验。

ORM Model（存储实体层）：与数据库表结构强绑定，包含了外键约束（ForeignKey）、索引（Index）以及主键生成策略。它关注的是数据如何在磁盘上落库。
如果把这两者混为一谈，一旦未来要修改数据库表字段，前端的 API 结构就会被迫一起发生破坏性变更，直接引发架构雪崩。

---

## 卡片 6：Repository 层的作用是什么？

Repository 用来隔离业务逻辑和数据库细节。  
业务层调用 repository，而不是直接写 SQLAlchemy 查询。

我的理解：
Repository 的职责是“让业务层对底层数据库一无所知”。Service 层或 Agent 状态机只需要调用 run_repo.save(agent_run)，至于底层是用 PostgreSQL、MySQL 还是内存字典，业务层根本不需要关心。这样设计有两个巨大的工程优势：

极度方便单元测试：我们可以随时通过依赖注入，把真实的 DB Repository 换成内存的 Mock Repository。

屏蔽多表联查的恶心细节：把 SQLAlchemy 的那些 join()、options(selectinload()) 脏活累活全部关进 Repository 的小黑屋里，让上层业务代码保持绝对的纯净。

---

## 卡片 7：为什么今天先不用 Alembic？

Day17 的重点是跑通落库链路。  
Alembic 是生产迁移工具，后续再引入可以降低学习负担。

我的理解：
Alembic 是做数据库版本迁移（Migration）的利器，类似于数据库的 Git。但今天我们的核心任务是把 AgentRun/RunStep/ToolCallRecord 这套庞大的树状对象成功写进数据库里。如果一上来就引入 Alembic，大家会陷入“修改了字段还要去跑 migration 脚本、处理冲突”的工具泥潭里。今天先用 Base.metadata.create_all() 简单粗暴地建表，等整条落库链路跑通、Schema 彻底稳定后，后续再引入 Alembic 才是最经济的工程节奏。

---

## 卡片 8：为什么每张表都保留 user_id？

方便权限过滤、审计、查询优化和后续多租户设计。

我的理解：
虽然从关系型数据库的规范（三范式）来看，RunStep 可以通过 run_id 间接查到 user_id，不需要冗余。但在生产环境中，横向越权（IDOR）是高危红线。如果每张表都有 user_id，当我们要查询或更新某个具体的 ToolCallRecord 时，Repository 就可以无脑加上一条强校验：.filter(ToolCallRecord.id == record_id, ToolCallRecord.user_id == current_user.user_id)。这确保了即便某个 id 泄露，黑客也绝无可能越权读写别人的数据。同时，它也为后续按用户维度进行分库分表（Sharding）打下了完美的伏笔。

---

## 卡片 9：为什么 JSON 字段要谨慎使用？

JSON 字段灵活，但可能存入过大内容或敏感信息。  
生产系统需要截断、脱敏和索引策略。

我的理解：
在 Agent 系统中，工具的入参和出参（arguments / tool_result）千奇百怪，用 JSONB（PostgreSQL）存储非常爽。但它的死穴在于：

无法在字段级别实施严密的数据库约束（如长度限制、非空约束），脏数据很容易偷偷滑入数据库。

极难做常规索引，一旦你想根据 JSON 内部的某个深度嵌套的 key 进行过滤查询，SQL 会直接退化为全表扫描（Full Table Scan），瞬间卡死生产数据库。因此，非必要不引入 JSON，引入则必须进行前置脱敏、截断，并克制查询欲望。

---

## 卡片 10：Day17 和 Day18 的关系

Day17 是同步写入数据库。  
Day18 会进一步用数据库 Repository 替换内存 Store，让查询和状态管理真正数据库化。

我的理解：
写出正确的 ORM 模型，在后台测试里成功把一个复杂的 AgentRun 对象以及它包含的多个 RunStep 和 ToolCallRecord 用一条事务顺利 commit() 进数据库的物理表里。明天的 Day 18，我们才会把这套打通的物理管道正式组装进 FastAPI 的业务主线中，用写好的 DB Repository 全面下线内存 Store，完成系统内核的无缝升级。