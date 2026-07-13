# Day13：认证体系升级

## 今日主题

从 demo 级 `X-User-ID` 升级为生产级 JWT `current_user`。

---

## 卡片 1：Authentication 认证

认证解决的是“你是谁”的问题。

例如：
- 用户名密码登录
- API Key
- JWT
- OAuth

我的理解：
认证是整个安全体系的第一道防线，它的本质是身份核验。服务端通过某种密码学手段或数据库比对，确认当前发起 HTTP 请求的物理人（或下游系统）在系统里到底映射为哪一个合法的 User 实体。没有认证，后面的权限和隔离都无从谈起。

---

## 卡片 2：Authorization 鉴权

鉴权解决的是“你能做什么”的问题。

例如：
- 普通用户能不能调用搜索工具
- 管理员能不能查看所有会话
- 免费用户每天能调用几次

我的理解：
认证（AuthN）是鉴权（AuthZ）的前置条件。认证先确认你是“员工 A”，鉴权再翻看员工守则，看看“员工 A”有没有进入财务机房的权限。在 Agent 工程中，鉴权往往与成本控制（Rate Limiting/Token Quota）和高危工具限制（HITL 级别分级）深度绑定。

---

## 卡片 3：为什么不能信任 X-User-ID？

- 因为 `X-User-ID` 是客户端自己传的，用户可以伪造。

- 例如：
- ```bash
- curl -H "X-User-ID: admin" ...

- 生产系统中，user_id 必须来自服务端验证过的 token。

我的理解：
“网络是不可信的，一切来自客户端的数据都是带有恶意的。” X-User-ID 只能用在公司内部微服务之间、且有硬防火墙隔离的私有网络里（即便如此也逐渐被内网 mTLS 取代）。在任何面向公网的网关层，不带签名校验的明文身份 ID 就是在给黑客写邀请函。

## 卡片 4：JWT 是什么？

JWT 是服务端签发的身份凭证，通常由三部分组成：

Header.Payload.Signature

Payload 中可以放：

sub，也就是 user_id
username
role
exp 过期时间

我的理解：

JWT 是无状态认证的银弹。它最大的好处是服务端“不需要查数据库/Redis”就能判定身份是否合法。服务端只要用自己的 SECRET_KEY 对收到的 Token 进行一次本地数学计算，如果算出来的签名和 Token 带的一致，且没过期，就能立刻信任里面的 user_id。

⚠️ 反直觉警告：Payload 部分只是 Base64 编码，它是明文的！任何人都可以解开看到里面的内容。 因此，千万不能在 JWT 的 Payload 里放密码、手机号、余额等敏感数据，它只防篡改，不防偷看。

## 卡片 5：Bearer Token 是什么？

Bearer Token 的请求格式：

Authorization: Bearer <access_token>

谁持有这个 token，谁就被认为是对应用户。

我的理解：

类比于现实世界中的“不记名飞机票”。机场安检口（网关）不关心这张票是怎么来的、是谁买的，只要这张票是真的（签名正确）、没过期，谁手里拿着这张票，谁就能登机。因此，Bearer Token 一旦泄露，黑客立刻拥有用户的完整化身。这也是为什么生产环境必须全量强制 HTTPS，防止 Token 在传输链路中被中间人截获（Sniffing）。

## 卡片 6：FastAPI Depends(get_current_user)

Depends(get_current_user) 可以把认证逻辑统一封装起来。

接口只需要写：

current_user: CurrentUser = Depends(get_current_user)

然后使用：

current_user.user_id

我的理解：

这体现了“面向切面编程（AOP）”的优雅。如果没有 Depends，你每一个业务 API（发消息、开会话、调工具）的第一行都得写一遍冗长的 Token 解密、异常捕捉代码。用 Depends 把认证剥离成一个纯净的拦截器，业务函数被保护在它身后，一睁眼拿到的就是 100% 可信的 current_user 对象，实现了安全代码与业务代码的完美解耦。

## 卡片 7：为什么认证是 session 隔离的基础？

session 查询必须基于可信 user_id：

session_store.get(session_id=session_id, user_id=current_user.user_id)

否则用户可以伪造身份访问别人的会话。

我的理解：
如果允许 user_id 伪造，那么 Day 11 写的会话锁、数据库路由全部形同虚设。只有当 user_id 来自于服务端本地通过 SECRET_KEY 密码学硬核背书的 JWT 时，Session.user_id == current_user.user_id 这一行 SQL 才能真正演变成一道把不同用户的数据死死隔绝在各自平行宇宙里的物理铁幕。