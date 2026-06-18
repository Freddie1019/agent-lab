"""Demo 1: 简单事实查询 - 一两步即可完成"""
import sys,os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from deep_research_agent.core.agent import ResearchAgent

if __name__ == "__main__":
    agent = ResearchAgent(max_steps=5)
    report = agent.run("Tavily Search API 免费版每月有多少次调用额度？")
    report.print_summary()