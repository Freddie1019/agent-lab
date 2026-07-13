# Week2 复盘：Agent 服务化

## 1. 本周目标

把 Week1 的命令行 / demo Agent 服务化，让它可以通过 HTTP 被用户访问。

---

## 2. 已完成能力

### 2.1 FastAPI 服务层

- server.py 组装 FastAPI app
- routes.py 提供 research / stream 接口
- sessions_routes.py 提供 session CRUD

### 2.2 SSE 流式输出

- AgentEvent
- to_sse()
- StreamingResponse
- 前端 index.html 展示事件

### 2.3 会话管理

- Session
- Message
- session_store
- session lock
- session history to LLM messages

### 2.4 流式错误处理

- 流前错误：HTTP 4xx / 5xx
- 流中错误：SSE event:error
- AgentErrorEvent
- interrupted / failed 状态

### 2.5 认证体系

- /auth/login
- /auth/me
- JWT
- get_current_user
- current_user.user_id
- session 按用户隔离

---

## 3. 当前完整链路

```text
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