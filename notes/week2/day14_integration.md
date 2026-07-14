# Day14：Week2 生产级联调

## Week2 完整链路图

text
## 用户登录
  ↓
POST /v1/auth/login    → 拿到user → 判断user/password是否正确 
  ↓
服务端签发 JWT     → 根据 user/JWT_SECRET_KEY 创建 token
  ↓
前端保存 token

## 用户创建会话
  ↓
POST /v1/sessions
  ↓
Depends(get_current_user)  → 拿到用户信息 user_id、user_name、role
  ├─ token 缺失 → HTTP 401
  ├─ token 过期 → HTTP 401
  └─ token 合法 → current_user
  ↓
session_store.create(user_id=current_user.user_id)  

## 用户发起流式 Agent 请求
  ↓
POST /v1/sessions/{session_id}/chat/stream
  ↓
Depends(get_current_user)  → 拿到用户信息 user_id、user_name、role 
  ↓
session_store.get(session_id, current_user.user_id)   → get当前会话id对应的会话内容
  ├─ session 不存在 → HTTP 404
  ├─ session 不属于当前用户 → HTTP 404
  └─ session 合法 → 进入下一步
  ↓
检查 session lock  → 防止并发
  ├─ locked → HTTP 409
  └─ unlocked → StreamingResponse
  ↓
构造 history -> 根据会话内容 拿到历史 messages
  ↓
return StreamingResponse(event_generator()) -> 返回流式响应

## event_generator()  -> 事件生成
  ├─ tool timeout → SSE event:error
  ├─ LLM error → SSE event:error
  ├─ max_steps → SSE event:error / warning
  └─ success → answer_complete + agent_complete
  ↓
session.is_processing = True 
  ↓
agent.stream_with_history()
  ↓
yield event.to_sse()
  ↓
complete / error / interrupted
  ↓
finally 持久化 user + assistant message
  ↓
session.is_processing = False

## 今日主题



把认证、会话、流式输出、错误处理串成完整生产链路。



---



## 卡片 1：系统联调是什么？



系统联调不是验证单个函数能不能跑，而是验证多个模块组合起来是否仍然正确。

在 Agent 服务里，需要联调：

- auth
- session
- stream
- agen
- tools
- error
- persistence

我的理解：

单元测试是保证“每个零件都是好的”，而联调是保证“组装起来的汽车能上路”。在 Agent 系统里，联调本质上是在验证一个有状态的闭环异步生命周期。从客户端发起请求的那一刻起，数据要在网络协议层（HTTP/SSE）、安全层（JWT）、业务内存层（Agent 状态机）、物理存储层（Redis/DB）之间完美无缝地流转，任何一个接口的字段对不上，整条链路就会瞬间雪崩。

---

## 卡片 2：为什么 Agent 服务比普通 API 更需要联调？


普通 API 通常是一次请求一次响应。
Agent 服务可能包含多轮推理、多次工具调用、长连接、状态写入和中途失败。



我的理解：

普通 CRUD 接口的链路极短（请求 $\rightarrow$ 查库 $\rightarrow$ 返回），输入 A 必定输出 B。但 Agent 服务是一个多步循环迭代系统：它在运行过程中会自己决定要不要调工具、调几次工具、什么时候结束。这种不确定性导致了它的生命周期极长，中间会伴随高频的数据库双写、流式事件广播。如果不通过全局联调把各种极端的时序、状态冲突跑通，根本无法在生产环境存活。

---

## 卡片 3：流前错误

流前错误发生在 StreamingResponse 返回之前。

例如：

- 认证失败
- token 过期
- session 不存在
- session 正在处理
- 请求参数错误

返回方式：

```text
HTTP 4xx / 5xx

我的理解：

这是系统的“看门大爷”。此时连接还是标准的短连接，响应头（Headers）还没有发送。我们可以心安理得地使用标准的 HTTP 状态码（如 401、403、422）和 Day 9 设计的 RFC 7807 统一 JSON 格式进行冷酷拦截。在这个阶段把脏请求、未授权请求干掉，是保护后端算力和长连接通道（File Descriptors 句柄）最经济的手段。

```

---

## 卡片 4：流中错误

流中错误发生在 StreamingResponse 已经开始之后。

例如：

LLM timeout

工具调用失败

搜索 API 限流

max_steps 超限

客户端断开

返回方式：

SSE event:error

我的理解：

这是流式架构最致命的“半路坠毁”。因为 HTTP 状态码已经定死在 200，你无法再通过抛出 HTTPException(status_code=500) 来告诉前端出错了。此时必须依靠我们在 Day 10 设计的一等公民错误事件（event: error），把错误以特殊的流式碎片包装并强行推给前端，随后优雅地断开连接，并立刻触发后台的资源清理程序（如释放会话锁）。

---

## 卡片 5：为什么认证失败不能是 SSE error？

认证失败说明用户没有资格启动这次 Agent run。
因此必须在流开始前返回 HTTP 401，而不是进入 event_generator。

我的理解：
如果认证失败还返回 200 OK 并吐出 event: error，这就犯了严重的语义混淆反模式。
第一，对前端不友好，前端必须先建立耗费资源的 SSE 连接才能发现自己没登录，极大地浪费了服务器连接并发数；第二，这属于典型的安全防护滞后。如果攻击者发起 DDoS 洪水攻击，你的服务器需要为每个非法请求都创建 StreamingResponse 和生成器线程，系统会瞬间因为句柄耗尽而挂掉。

---


## 卡片 6：session 隔离

session 隔离的核心是：


session_store.get(

session_id=session_id,

user_id=current_user.user_id,

)

不能只按 session_id 查询，否则用户可能访问别人的会话。

我的理解：

绝对不能为了图省事写成 session_store.get(session_id)。因为 session_id（如 UUID 或自增 ID）一旦被黑客猜到或通过撞库（Enumeration Attack）拿到，就能直接横向越权查到别人的隐私。必须将 user_id（来自不可篡改的 JWT）和 session_id 绑定为联合唯一索引。在逻辑上，“不是我的 Session，对我就等同于不存在（返回 404）”，这才是工业级的防腐隔离。


## 卡片 7：回归测试

回归测试是指新增功能后，验证旧功能是否仍然正常。

Day14 需要回归：


Day10 SSE
Day11 session
Day12 error
Day13 auth

我的理解：

今天加了 JWT 认证（Day 13），我很可能一不小心把 Day 10 的纯流式通道给改挂了（例如漏了跨域 Header），或者把 Day 11 的会话追加逻辑写错了。回归测试的目的就是通过写好的自动化集成脚本（如 FastAPI 的 TestClient），把之前的典型正常流、异常流全部重新跑一遍，确保新功能的加入没有产生任何隐蔽的次生灾难。


## 卡片 8：故障注入

故障注入是主动制造错误，用来验证系统在异常场景下是否健壮。
Agent 系统必须做故障注入，因为 LLM 和工具调用都具有不确定性。

我的理解：

在 Agent 系统中，故障是常态——大模型会突然吐出坏掉的 JSON、搜索 API 会限流、用户会突然在第 3 秒关掉浏览器。我们必须在联调中“主动使坏”：比如人为让工具返回 429 Too Many Requests，或者在流到一半时强行 Kill 掉外部进程。看系统是会卡死PENDING，还是能完美捕捉并吐出 event: error 且安全写入残卷日志。在开发环境被注入过 100 次的系统，才能在生产环境挺过第 1 天。

## 卡片 9：Week2 完整链路

login
↓
JWT
↓
current_user
↓
session
↓
chat/stream
↓
Agent
↓
tools
↓
SSE events
↓
session messages

我的理解：

[1. 登录网关] login ──► 校验凭证，使用 SECRET_KEY 签发令牌
       │
[2. 安全契约] JWT ──► 客户端持有并在每个 HTTP 头部携带 Bearer Token
      │
[3. 身份注入] current_user ──► FastAPI Depends 自动拦截、解密，注入合法上下文
      │
[4. 确权路由] session ──► 依据联合查询 user_id + session_id 严密卡位，锁死独立宇宙
      │
[5. 管道升级] chat/stream ──► 验证通过，下发 200 OK 响应头，正式激活 Async Generator
      │
[6. 大脑驱动] Agent ──► 启动循环状态机，动态读取历史，向大模型发起异步网络推理
      │
[7. 副作用执行] tools ──► 触发表层物理世界（搜索、数据库、发信），捕获故障并清洗
      │
[8. 碎片广播] SSE events ──► 实时将 thought/tool_call/error 切分成 \n\n 事件流推向前端
      │
[9. 状态归档] session messages ──► 处理完毕或中途断连，触发清道夫收尾，干净持久化归档

这幅链路图就是你这两周全部心血的宏观沙盘！它不仅是一条代码流，更是一套责任分明、层层设防的工业级架构体系。每一个节点都各司其职：前置节点负责防守（安全、鉴权、隔离），中置节点负责推理（Agent、LLM），后置节点负责留痕与清理（SSE、Persistence）。

