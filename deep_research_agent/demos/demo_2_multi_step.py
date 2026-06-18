"""Demo 2: 多步研究 - 需要分别查询多个对象再综合"""
import sys,os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from deep_research_agent.core.agent import ResearchAgent

if __name__ == "__main__":
    agent = ResearchAgent(max_steps=10)
    report = agent.run(
        "对比 LangGraph、CrewAI、AutoGen 这三个 Agent 框架，"
        "分别说明它们的设计理念、主要适用场景"
    )
    report.print_summary()