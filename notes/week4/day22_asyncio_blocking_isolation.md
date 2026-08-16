# Day22 AsyncIO 与阻塞隔离

## 卡片1：Event Loop
定义：负责调度协程的单线程循环。
当前作用：同时推进 SSE、Heartbeat、数据库 I/O、断连检测和其他请求。
我的理解：
Event Loop 是 Python 异步并发的“调度中枢”。它在单线程内利用 CPU 游刃有余地切换各种非阻塞 I/O 任务。在 Agent 系统中，当 Agent 等待 LLM 吐 Token 或数据库写盘时，Event Loop 不会傻等，而是立刻切去处理 SSE 推送、刷心跳（Heartbeat）或响应其他用户的 HTTP 请求。它是 FastAPI 实现高并发、不卡顿的物理基础。

## 卡片2： Coroutine
定义：调用 async def 得到的可暂停执行对象。
当前作用：Agent 流、Repository 和 Heartbeat 都通过协程运行。
我的理解：
Coroutine（协程）是“可以随时按暂停键的代码块”。与传统函数一旦执行必须通到底不同，带有 async def 的协程遇到 await 时，会主动把 CPU 控制权交还给 Event Loop，并说：“我这里需要等 I/O，你先去干别的。” Agent 的 Reasoning 循环、Repository 的异步读写、SSE 事件生成器本质上都是协程，它们是把长任务拆解为可协作片段的语言级原语。

## 卡片3：Task
定义：被 Event Loop 调度、带有完成/异常/取消状态的协程执行实例。
当前作用：Heartbeat 和响应性测试中的慢工具都以 Task 运行。
我的理解：
如果 Coroutine 是“写在纸上的剧本”，那么 asyncio.Task 就是“正在舞台上上演的剧”，它是把协程包装后交给 Event Loop 管理的独立执行实体。在 Agent 系统中，像后台心跳探针（Heartbeat Loop）、后台异步落盘、以及超时检测，都需要包装成独立的 Task 在后台“悄悄并行运行”，并随时可以通过 task.cancel() 强行打断。

## 卡片4：Blocking I/O
定义：占住当前线程直到操作完成的 I/O。
当前作用：同步 OpenAI、Tavily、同步 httpx 和审计文件写入。
我的理解：
Blocking I/O（阻塞式 I/O）是 AsyncIO 架构中的第一杀手。如果有人在 async def 内部直接调用了同步的 requests.get()、同步的第三方 SDK 或直接操作本地文件系统，该线程就会被彻底卡死，Event Loop 会整个瘫痪，导致所有其他用户的 SSE 流断连、心跳超时、服务陷入假死。在异步框架里，绝对不能让任何 Blocking I/O 直接露天运行。

## 卡片5：asyncio.to_thread()
定义：把同步调用送入线程池，并异步等待结果。
当前作用：隔离现有同步工具栈。
我的理解：
这是将现有“同步工具生态”接入异步 Agent 系统的安全隔离舱。在真实开发中，很多现成的第三方 SDK（如旧版工具包、同步文件写入、传统 SQL 驱动）没有异步接口。使用 asyncio.to_thread() 可以把这些阻塞操作甩给后台的 Worker 线程池去跑，主 Event Loop 只需要在外面 await 它的结果，既不用重写现有工具，又保证了主事件循环的绝对畅通。

## 卡片6：Timeout Boundary
定义：为外部等待设置最大业务时间预算。
当前作用：限制 LLM 与工具等待，防止永久挂起。
我的理解：
Timeout Boundary（超时边界）是防止 Agent 被外部慢速服务“无休止关押”的防爆计时器。大模型 API 可能会卡住 60 秒不出字，第三方爬虫工具可能在网络死锁中无限等待。通过 asyncio.timeout() 或 asyncio.wait_for() 建立硬性时间预算（Time Budget），一旦超时立刻抛出 TimeoutError 并触发降级/熔断，确保系统的响应时间具有确定性上限。

## 卡片7：Cancellation Propagation
定义：取消沿 await 链向下传播，并通过 finally 完成资源清理。
当前作用：客户端断连、服务退出和未来任务取消都依赖它。
我的理解：
Cancellation Propagation（取消信号传播）是异步长任务中优雅清理资源的急停电闸。当客户端用户点击“取消生成”断开 SSE 连接时，FastAPI 会向当前 Task 发起 cancel() 信号。这个信号会顺着 await 调用链一路向下传递，触发 CancelledError 异常，并激活所有的 try...finally 或 Context Manager（如释放 DB 连接、记录 interrupted 状态），确保不会留下任何无脑耗费算力的“幽灵 Task”。