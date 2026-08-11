# Day19：Agent 中断恢复 
## 卡片 1：Regenerate 

Regenerate 是从原始用户问题重新执行整个 Agent 流程。 

我的理解： 这相当于游戏里的“放弃本局，重新开局”。当用户对 Agent 跑出来的整体结果不满意、或者之前的推理路线彻底走偏（进入了死循环/幻觉陷阱）时，Regenerate 是最好的选择。它不会试图去修复上一次失败的残局，而是直接将旧 Run 标记为废弃/取消，重新初始化上下文，从 Step 1 开始干净利落地重新思考。
--- 

## 卡片 2：Resume 

Resume 是从最近的稳定 Checkpoint 恢复上下文，并创建新的 AgentRun 继续执行。 

我的理解： 这相当于游戏里的“读取存档（Load Save）”。如果一个复杂的 Agent 任务一共需要 5 步（比如：1.检索 2.分析 3.调 API 写库 4.汇总 5.生成报告），在 Step 3 执行完后服务器突然断电了。Resume 的核心能力就是不重复做 Step 1 和 Step 2，而是直接从 Step 3 结束时的快照中把上下文“装载”回内存，创建新的子 Run 顺着 Step 4 接着吐出结果

--- 
## 卡片 3：Retry 

Retry 是只重新执行失败的步骤或工具。 Retry 必须考虑工具幂等性和副作用。 

我的理解： 这相当于游戏里的“原地重试”。比如 Agent 在 Step 2 调用 Search API 时遭遇了网络抖动（429/503），此时既不需要重新启动整个 Agent，也不需要做复杂的上下文恢复，只需要针对这个特定的工具函数实施指数退避（Exponential Backoff）重试。注意：Retry 必须死死盯住工具的“幂等性”，绝不能对有强副作用的非幂等工具（如扣款、发信）盲目自动重试！

--- 

## 卡片 4：Checkpoint 

Checkpoint 是能够恢复 Agent 执行的状态快照。 它应包含 messages_snapshot、step_index 和最后稳定事件。 

我的理解： Checkpoint 是 Resume 能成功运行的物理基石。它不能是一堆无序的日志，而必须是一个结构化的序列化状态包，通常至少包含：
messages_snapshot：截至当前步骤，喂给大模型的完整 Message 历史数组。
step_index：当前执行到了第几步。
last_stable_event_id：前端/系统收到的最后一个稳定事件锚点。
只有拥有了 Checkpoint，新拉起来的进程才能在零上下文丢失的前提下瞬间“复活”。

--- 

## 卡片 5：RunStep 和 Checkpoint 的区别 

RunStep 用于观察和审计。 Checkpoint 用于恢复执行。 

我的理解： 
RunStep（黑匣子日志）：是增量写入的，里面可能包含大量的中间态流式碎片（Thought 吐了一半、工具调用到一半抛了异常）。它的使命是给人类做审计、可视化展示和性能分析，包含了许多“脏/未完成”的数据。
Checkpoint（状态快照）：是只在关键确定性节点生成的结构化快照。它必须保证数据的“绝对干净”——即删除了未完成的临时 Event，只保留大模型和工具确认完结后的完整 Message 状态，专为引擎反序列化恢复服务。

--- 

## 卡片 6：为什么恢复要创建新 Run？ 

旧 Run 是已经发生的历史事实。 恢复应该创建子 Run，保留 parent_run_id 和 recovery_mode。 

我的理解： 绝对不能为了图省事，直接把崩溃的旧 Run_001 状态从 failed 改回 running 并继续在上面写数据！因为旧 Run 在崩溃前可能已经向前端推送了部分流式事件，或者保留了崩溃时的 Error 堆栈。如果在旧 Run 上直接叠加，会导致历史执行轨迹被污染破坏。正确的做法是：将旧 Run_001 的状态永久封存为 interrupted 或 failed，然后创建一个全新的 Run_002，并标记 parent_run_id = Run_001。这符合追加只读（Append-Only）的生产级审计原则。 

--- 

## 卡片 7：Write-Ahead Persistence 

用户消息必须在 Agent 执行前写入数据库，确保进程突然终止后仍然可以恢复原始问题。 

我的理解： 如果在 HTTP 请求进来后，Agent 立刻在内存里启动生成器去调大模型，打算等“跑完了再一起存库”，那么只要在生成过程中服务器发生宕机，用户的这条 Prompt 就会在内存中彻底蒸发，系统连“用户刚才问了什么”都不知道，更谈不上后续的恢复了。必须遵循“请求先落盘，大脑再思考”的铁律，确保任何时刻遭遇物理毁伤，数据库里都有据可查。

--- 

## 卡片 8：为什么 tool_call 不是稳定检查点？ 

工具开始后可能已经产生副作用，但结果尚未明确。 此时恢复可能重复执行工具。 

我的理解： 当 LLM 吐出 tool_call: transfer_money(amount=100) 时，如果在这个瞬间保存 Checkpoint 并断线：系统无法得知这个转账请求到底是“还没发出”、“正在网络中传输”、还是“银行已经扣了款但回执没传回来”。如果恢复时从这个 Checkpoint 重跑，Agent 就会再次发起一次 transfer_money，造成可怕的“二次扣款”。只有当工具执行完毕并拿到了明确的 tool_result 后，这个节点才能被升级为稳定的 Checkpoint！

--- 

## 卡片 9：工具幂等性 

幂等工具重复执行多次，最终效果和执行一次相同。 非幂等工具不能随意自动重试。 

我的理解： 

天然幂等工具：get_weather(city="Beijing")（查询类）、set_user_status(status="active")（绝对覆盖赋值类）。这类工具在 Retry 或 Resume 时可以无脑自动重试。

非幂等工具：send_email(...)（发信）、post_payment(...)（扣款）、append_log(...)（追加日志）。这类工具重试一次就会多发一封邮件/多扣一次钱。对于非幂等工具，在恢复链路中必须加入“人工确认（HITL）”或“唯一幂等键（Idempotency Key）”进行防御。

--- 

## 卡片 10：恢复血缘 

恢复后的新 Run 应记录 parent_run_id、mode 和 checkpoint_id，形成完整执行链路。 

我的理解： 

通过在 AgentRun ORM 模型中保留：

parent_run_id（父 Run ID）

recovery_mode（恢复模式：resume / regenerate / retry）

checkpoint_id（基于哪个快照恢复）

我们就可以在数据库里构建出一幅完整的执行树状血缘图：

Plaintext
Run_001 (Failed at Step 3)
   └── Run_002 (Mode: Resume, Checkpoint: Step_2_Snapshot)
          └── Run_003 (Mode: Retry Tool, Tool: SearchAPI) -> Completed
这不仅让系统的可观测性（Observability）拉满，也为后续分析“哪些步骤最容易崩溃、哪些恢复模式成功率最高”提供了极具价值的统计元数据。