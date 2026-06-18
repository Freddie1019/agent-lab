"""
研究 Agent 的工具集
整合：真实工具 + 危险等级标注 + 速率限制
"""
import os,sys
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.real_tools import (
    web_search, fetch_url,
    REAL_TOOLS_SCHEMA, REAL_TOOLS_REGISTRY,
)
from shared.safety import ToolMetadata, DangerLevel

# 研究 Agent 的工具集（注意：这里都是只读，所以都是 GREEN）
RESEARCH_TOOLS = {
    "web_search": ToolMetadata(
        name="web_search",
        func=web_search,
        danger_level=DangerLevel.GREEN,
        description="搜索互联网获取最新信息",
    ),
    "fetch_url": ToolMetadata(
        name="fetch_url",
        func=fetch_url,
        danger_level=DangerLevel.GREEN,
        description="抓取指定 URL 的网页内容",
    ),
}

RESEARCH_TOOLS_SCHEMA = REAL_TOOLS_SCHEMA  # 复用

def get_tool_by_name(name: str):
    return RESEARCH_TOOLS.get(name)