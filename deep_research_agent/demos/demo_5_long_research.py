"""Demo 5: 长任务 - 多个子问题串联，触发上下文压缩"""
import sys,os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from deep_research_agent.core.agent import ResearchAgent

if __name__ == "__main__":
    agent = ResearchAgent(
        max_steps=15,
        max_context_tokens=3000,  # 故意设小一点，触发压缩
    )
    report = agent.run(
        "我想全面了解 2025 年 LLM Agent 的技术发展现状，请回答：\n"
        "1. 主流的 Agent 设计范式有哪些（如 ReAct、Plan-and-Execute 等）？\n"
        "2. 多 Agent 协作目前的主要技术路线是什么？\n"
        "3. Anthropic 的 MCP 协议是什么？\n"
        "4. 这三个话题之间的内在联系是什么？"
    )
    report.print_summary()