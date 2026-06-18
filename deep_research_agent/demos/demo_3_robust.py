"""Demo 3: 故障注入下的健壮性 - 30% 工具失败率"""
import sys,os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from deep_research_agent.core.agent import ResearchAgent
from shared.fault_injector import FaultInjector
from shared import real_tools

if __name__ == "__main__":
    # 用故障注入器包装真实工具
    injector = FaultInjector(
        timeout_rate=0.15,
        rate_limit_rate=0.10,
        unavailable_rate=0.05,
    )
    
    # Monkey-patch（仅用于 demo）
    real_tools.web_search = injector.wrap(real_tools.web_search)
    real_tools.fetch_url = injector.wrap(real_tools.fetch_url)
    
    agent = ResearchAgent(max_steps=12)
    report = agent.run("MCP（Model Context Protocol）是什么？谁提出的？")
    
    report.print_summary()
    injector.report()