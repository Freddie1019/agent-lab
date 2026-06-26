"""
单独测试 Agent.stream() 不经过 HTTP
"""
import asyncio
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from deep_research_agent.core.agent import ResearchAgent

async def main():
    agent = ResearchAgent(max_steps=8, verbose=False)
    
    async for event in agent.stream("LangGraph 是什么？请简要介绍"):
        print(f"\n━━━ Event: {event.type} (step={event.step}) ━━━")
        print(f"{event.data}")


if __name__ == "__main__":
    asyncio.run(main())