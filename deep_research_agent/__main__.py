# deep_research_agent/__main__.py
from deep_research_agent.core.agent import ResearchAgent

agent = ResearchAgent()
report = agent.run("2025 年最受欢迎的开源 Agent 框架是哪几个？")
report.print_summary()