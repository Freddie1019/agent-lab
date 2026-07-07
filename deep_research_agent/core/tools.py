"""
研究 Agent 的工具集
整合：真实工具 + 危险等级标注 + 速率限制
支持通过环境变量 FAULT_INJECTION 启用故障注入
"""
import os,sys
import atexit
sys.path.insert(0,os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.real_tools import (
    web_search, fetch_url,
    REAL_TOOLS_SCHEMA, REAL_TOOLS_REGISTRY,
)
from shared.safety import ToolMetadata, DangerLevel

# ===== 故障注入（通过环境变量控制） =====
_fault_enabled = os.getenv("FAULT_INJECTION", "0") == "1"
_fault_injector = None

if _fault_enabled:
    from shared.fault_injector import FaultInjector
    _fault_injector = FaultInjector(
        timeout_rate=float(os.getenv("FAULT_TIMEOUT_RATE", "0.30")),
        rate_limit_rate=float(os.getenv("FAULT_RATE_LIMIT_RATE", "0.20")),
        unavailable_rate=float(os.getenv("FAULT_UNAVAILABLE_RATE", "0.00")),
        garbage_rate=float(os.getenv("FAULT_GARBAGE_RATE", "0.00")),
    )
    _web_search = _fault_injector.wrap(web_search)
    _fetch_url = _fault_injector.wrap(fetch_url)
    print(f"⚠️ 故障注入已启用 "
          f"(timeout={_fault_injector.timeout_rate}, "
          f"rate_limit={_fault_injector.rate_limit_rate})")
    
    # 服务器关闭时自动输出统计
    def _print_fault_report():
        _fault_injector.report()
    atexit.register(_print_fault_report)
else:
    _web_search = web_search
    _fetch_url = fetch_url

# 研究 Agent 的工具集（注意：这里都是只读，所以都是 GREEN）
RESEARCH_TOOLS = {
    "web_search": ToolMetadata(
        name="web_search",
        func=_web_search,
        danger_level=DangerLevel.GREEN,
        description="搜索互联网获取最新信息",
    ),
    "fetch_url": ToolMetadata(
        name="fetch_url",
        func=_fetch_url,
        danger_level=DangerLevel.GREEN,
        description="抓取指定 URL 的网页内容",
    ),
}

RESEARCH_TOOLS_SCHEMA = REAL_TOOLS_SCHEMA  # 复用

def get_tool_by_name(name: str):
    return RESEARCH_TOOLS.get(name)