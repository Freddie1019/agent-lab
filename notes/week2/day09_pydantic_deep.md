# Day 9 概念卡片：Pydantic 深入 + API 契约设计

---

## 卡片 1：Pydantic v2 的双层架构 🤖

Pydantic v2 = Python 接口层 + Rust 核心（pydantic-core）。

**性能秘密**：
- 你写的 `class Model(BaseModel)` 是 Python 声明
- 校验、序列化的实际工作由 Rust 执行
- 比 v1 快 5-50 倍

**工程师素养**：选 Python 依赖时不只看功能，也看底层语言。Rust 实现的 Python 库（Pydantic、Polars、Ruff）在 2024 年集体崛起，根本原因是解决了 Python 性能瓶颈。

---

## 卡片 2:Pydantic 的三层校验体系 🤖

1. **类型自动校验**：`field: int`
2. **Field 约束（声明式）**：`Field(..., ge=0, le=100, min_length=1)`
3. **Validator（命令式）**：`@field_validator` / `@model_validator`

**field_validator**：单字段校验 + 清洗  
**model_validator(mode="after")**：所有字段校验完后做跨字段校验

**执行顺序**：类型转换 → Field 约束 → field_validator → model_validator。任一步失败即抛 ValidationError，FastAPI 自动返回 422。

---

## 卡片 3:RFC 7807 统一错误格式 🤖

业界标准的 HTTP 错误响应格式：

```json
{
  "type": "https://api.example.com/errors/rate-limit",
  "title": "Rate Limit Exceeded",
  "status": 429,
  "detail": "...",
  "instance": "/v1/research/abc123",
  "request_id": "req_xxx",
  "errors": []
}
```

**好处**：前端只解析一种格式。错误可分类、可追溯。

---

## 卡片 4：防腐层（Anti-Corruption Layer）🤖

DDD 经典模式：边界模型（DTO，宽松） ≠ 领域模型（严格，业务内部）。
前端 JSON ──► DTO(ResearchRequest) ──► 领域(ResearchTask) ──► 业务(Agent)

（宽松，向前兼容）          （严格，不变）
**好处**：API 改字段名 → 只改 `from_api_request` 一处。业务逻辑完全不感知 API 变化。这就是 Stripe / Shopify 这种 API 平台能长期稳定的秘密。

---

## 卡片 5：API 版本管理的工程意义 ✍️

请基于今天的实战回答：

- 你今天把 `/research` 改成 `/v1/research`。这个改动表面只是 URL 加了 `v1/`，但背后承诺了什么？
- 在 URL 前增加v1后实则是与客户承诺了一份向后兼容性的契约，在没有提前通知或者是提供其他兼容方案时
- v1/ 接口的 URL、请求方法、必填参数、返回的 JSON 结构、状态码甚至核心业务逻辑绝对不会发生破坏性变更（Breaking Change）。

- 设想 6 个月后你想给 ResearchRequest 加一个必填字段，**为什么不能直接在 v1 加，而必须开 v2**？
- 从客户端视角来看，他们可能是第三方公司，移动端APP，甚至可能是写死在物联网设备里面的脚本，不会频繁更新客户端代码或SDK，所以
- 如果在 v1 里将新字段设置为必填，那么没传这个字段的旧客户端请求就会返回 422 错误，因此必须开辟新版本 v2 使新旧版本并存，
- 旧客户端继续安全跑在 v1 即可
- 提示：从"客户端的视角"思考——他们可能 1 年都不升级 SDK

---

## 卡片 6：Pydantic 在 Agent 工程中的多重角色 ✍️

Pydantic 在 Agent 工程中至少有 4 个不同角色（你前 9 天已经全见过了）。请列出来，并说明每个角色对应什么场景：

1. 输入防御和校验契约：对前端传来的 HTTP 请求（JSON）进行严格的类型、边界校验，将脏数据拦截在业务逻辑之外
2. LLM 结构化输出的 Schema：将Pydantic转换为JSON Schema喂给大模型，强制让大模型以 100% 顺从的结构化 JSON 吐出思考结果
3. 系统环境与配置管理：利用 pydantic-settings 自动读取 .env 文件和系统环境变量，做类型校验（如确保 PORT 是 int，OPENAI_API_KEY 存在），构建安全的全局配置字典。
4. 内部业务状态与核心领域模型：在防腐层内部，作为 Agent 核心大脑的内部状态承载者（如 ResearchTask、AgentState），用于追踪步骤、持久化数据、驱动状态机。

提示：Day 2 见过、Day 8 见过、Day 9 见过两次。

---

## 卡片 7：防腐层 vs 简单 DTO ✍️

任务 5 里你引入了 `ResearchTask` 领域模型。但有人会说："这不就是把 `ResearchRequest` 复制了一遍吗？多此一举！"

请回答：

- 防腐层在什么情况下"看起来多余"，但实际上必须有？
- 外部 API 结构及其肮脏或不确定：当Agent要对接多个第三方搜索API，或老旧的ERP系统，他们返回的格式经常变，或者字段及其晦涩
- 多渠道输入：同一个Agent核心业务，既支持 Web API调用，又支持微信群聊消息，此时各个渠道都有各自的DTO,但进入防腐层后，一律转化为
- 严格的领域模型，这样 API 换字段、换平台，内部 Agent 代码一行也不需要更改
- 防腐层在什么情况下"真的多余"，简单 DTO 就够了？
- 1.业务纯粹且生命周期短
- 2.处于孵化阶段需快速成型的Demo
- 提示：从"API 变化频率"和"业务复杂度"两个维度思考

---

## 卡片 8：今天最关键的工程认知 ✍️

请用 2-3 句话总结：
- 从 Day 8 的"能跑 FastAPI" 到 Day 9 的"工业级 API 契约"，你的认知变化是什么？
- 哪个概念你以前模糊（Validator / Settings / 版本管理 / 防腐层），今天清晰了？
- 从“能跑”到“工业级契约”的质变：
- 以前觉得写 API 就是“把 Python 函数跑在网上，数据能传进去就行”；今天明白，工业级 API 是一场全方位的合同管理。
- 你必须用 Pydantic 构建起坚固的防腐层守住内脏（业务逻辑），用 RFC 7807 统一话术（错误格式），用版本号对外部用户负责。
- 最清晰的概念：
- 以前总把校验写在业务逻辑里（满屏的 if ），今天被 Validator 的三层校验体系彻底洗脑了：声明式 Field 负责看门，
- Field Validator 负责洗刷脏字段，Model Validator 负责跨字段宏观调控，把乱七八糟的请求治理得井井有条。

---

## 还不明白的地方
（列出来下次问我）