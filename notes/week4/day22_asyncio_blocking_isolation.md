# Day22 AsyncIO 与阻塞隔离

## 卡片1：Event Loop
定义：负责调度协程的单线程循环。
当前作用：同时推进 SSE、Heartbeat、数据库 I/O、断连检测和其他请求。
我的理解：TODO

## 卡片2： Coroutine
定义：调用 async def 得到的可暂停执行对象。
当前作用：Agent 流、Repository 和 Heartbeat 都通过协程运行。
我的理解：TODO

## 卡片3：Task
定义：被 Event Loop 调度、带有完成/异常/取消状态的协程执行实例。
当前作用：Heartbeat 和响应性测试中的慢工具都以 Task 运行。
我的理解：TODO

## 卡片4：Blocking I/O
定义：占住当前线程直到操作完成的 I/O。
当前作用：同步 OpenAI、Tavily、同步 httpx 和审计文件写入。
我的理解：TODO

## 卡片5：asyncio.to_thread()
定义：把同步调用送入线程池，并异步等待结果。
当前作用：隔离现有同步工具栈。
我的理解：TODO

## 卡片6：Timeout Boundary
定义：为外部等待设置最大业务时间预算。
当前作用：限制 LLM 与工具等待，防止永久挂起。
我的理解：TODO

## 卡片7：Cancellation Propagation
定义：取消沿 await 链向下传播，并通过 finally 完成资源清理。
当前作用：客户端断连、服务退出和未来任务取消都依赖它。
我的理解：TODO