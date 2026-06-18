# Deep Research Agent

> 一个能自主搜索互联网、迭代研究并产出引用报告的 AI 研究助手。从零手写的 ReAct Agent，集成生产级工程特性。

[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

## ✨ Features

- 🧠 **自主多步推理**：基于 ReAct 模式的工具调用循环
- 🔍 **真实互联网搜索**：集成 Tavily Search API
- 📚 **智能上下文管理**:支持滑动窗口 / 自动摘要两种策略
- 🛡️ **生产级护栏**：
  - 工具级 Circuit Breaker（电路熔断器）
  - HITL（Human-in-the-Loop）危险操作拦截
  - 结构化审计日志
  - 故障注入测试
- 💰 **成本可控**：Token 预算上限 + 实时统计
- 📊 **完整运行报告**：步数、token、成本、HITL 触发、错误明细

## 📦 安装

需要 Python 3.11+ 和 [uv](https://github.com/astral-sh/uv) 包管理器。

```bash
git clone https://github.com/yourname/agent-lab.git
cd agent-lab
uv sync
```

配置 API Key（创建 `.env` 文件）：

```bash
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
TAVILY_API_KEY=tvly-xxx
```

> Tavily 提供免费 1000 次/月，注册：https://tavily.com

## 🚀 快速开始

```bash
# 基础查询
uv run python -m deep_research_agent.cli.main "2025 年最火的开源 Agent 框架"

# 控制步数和预算
uv run python -m deep_research_agent.cli.main \
    "对比 LangGraph 和 CrewAI" \
    --steps 12 \
    --budget 80000

# 保存运行报告
uv run python -m deep_research_agent.cli.main \
    "MCP 协议详解" \
    --save-report ./report.json
```

## 📺 Demo

运行 5 个内置 demo 见识 Agent 的能力：

```bash
uv run python -m deep_research_agent.demos.demo_1_simple       # 简单查询
uv run python -m deep_research_agent.demos.demo_2_multi_step   # 多步对比
uv run python -m deep_research_agent.demos.demo_3_robust       # 故障注入测试
uv run python -m deep_research_agent.demos.demo_4_hitl         # HITL 触发
uv run python -m deep_research_agent.demos.demo_5_long_research # 长任务+压缩
```

## 🏗️ 架构
┌─────────────────────────────────────────────────────────┐

│              CLI / Application Layer                     │

│           (deep_research_agent/cli/)                     │

├─────────────────────────────────────────────────────────┤

│             ResearchAgent (Business)                     │

│        ReAct Loop + Orchestration + Reporting           │

│           (deep_research_agent/core/)                    │

├─────────────────────────────────────────────────────────┤

│              Capability Layer                            │

│  ContextManager │ Safety │ Audit │ CircuitBreaker      │

│                  (shared/)                               │

├─────────────────────────────────────────────────────────┤

│            Infrastructure Layer                          │

│      LLMClient │ TokenCounter │ Tavily │ HTTPX         │

└─────────────────────────────────────────────────────────┘
## 🧠 核心设计原则

### 1. ReAct 循环作为内核
所有"Agent 自主性"的来源 = `while True` 循环 + LLM 的 `finish_reason` 状态机判断。

### 2. 分层错误处理（Graceful Degradation）
基础设施层自动重试 → 工具层语义化错误 → Agent 层向用户坦白

### 3. 工程护栏不可被 Prompt 绕过
HITL、Circuit Breaker、审计日志全部在代码层强制执行，不依赖 LLM 的"听话"

### 4. 一切失败都是设计的一部分
故障注入测试（chaos engineering）证明 Agent 能在 30% 工具失败率下仍然产出可用答案

## 📊 性能基准（gpt-4o-mini）

| Demo | 步数 | Token | 成本 | 耗时 |
|------|-----|-------|------|------|
| 简单查询 | 2-3 | ~3k | ~$0.001 | 5-10s |
| 多步对比 | 6-8 | ~15k | ~$0.005 | 20-30s |
| 长任务 | 10-15 | ~40k | ~$0.015 | 60-90s |

## 🛣️ Roadmap

- [ ] 升级 ReAct → Plan-and-Execute 模式
- [ ] 添加流式输出（SSE）
- [ ] 持久化对话历史（PostgreSQL）
- [ ] FastAPI 服务化
- [ ] 多 Agent 协作

## 📝 License

MIT