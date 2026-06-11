"""
真实工具集
- web_search: 基于 Tavily 的搜索
- fetch_url: 基于 trafilatura 的网页抓取（备用）

包含工业基础设施：
- 超时
- 重试（指数退避）
- 结果体积控制
"""
import os
from certifi import contents
import httpx
import trafilatura
from dotenv import load_dotenv
from tavily import TavilyClient
from shared.rate_limiter import tracker
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

load_dotenv()
_tavily_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ====== 工具 1：web_search ======
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException, ConnectionError)),
    reraise=True,
)
def web_search(query: str, max_results: int = 5) -> str:
    """
    搜索互联网，返回最相关的几条结果摘要。
    使用 Tavily 搜索引擎，结果已自动清洗为可读文本。
    """
    try:
        response = _tavily_client.search(
            query=query,
            search_depth="basic",
            max_results=max_results,
            include_answer=False,
        )
    except Exception as e:
        return f"搜索失败: {type(e).__name__}: {e}"
    
    if not response.get("results"):
        return f"未找到与 '{query}' 相关的结果"
    
    # 格式化成 LLM 友好的文本
    lines = [f"搜索查询： {query}\n"]
    for i, r in enumerate(response["results"], 1):
        # ★ 关键：单条结果做截断，防止 token 爆炸
        content = r["content"]
        if len(content) > 500:
            content = content[:500] + "...[已截断]"
        lines.append(f"[结果 {i}] {r['title']}")
        lines.append(f"  URL: {r['url']}")
        lines.append(f"  摘要: {content}")
        lines.append("")
    return "\n".join(lines)

# ===== 工具 2: fetch_url（备用，用于抓特定 URL）=====
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def fetch_url(url: str, max_chars: int = 3000) -> str:
    """
    抓取一个 URL 的主要文本内容（自动清洗导航/广告/版权信息）。
    使用 trafilatura 提取正文。
    """
    try:
        with httpx.Client(
            timeout=10.0,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ResearchAgent/1.0)"
            },
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPStatusError as e:
        return f"抓取失败: HTTP {e.response.status_code} - {url}"
    except Exception as e:
        return f"抓取失败: {type(e).__name__} - {url}"
    
    # 用 trafilatura 提取正文（自动去广告/导航/版权）
    extracted = trafilatura.extract(response.text)
    if not extracted:
        return f"无法从 {url} 提取正文内容（可能是 JS 渲染或非文章页面）"
    
    if len(extracted) > max_chars:
        extracted = extracted[:max_chars] + f"\n\n...[已截断，原文共 {len(extracted)} 字符]"
    
    return extracted

# ===== 工具 Schema 定义 =====
REAL_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "搜索互联网获取最新信息。当需要查询实时信息、最新动态、不确定的事实时使用。返回多条相关网页的标题、URL 和内容摘要。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索查询词，使用关键词形式效果最好，如 '2025 开源 Agent 框架'"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "返回的结果数量，1-10，默认 5",
                        "default": 5
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "抓取指定 URL 的网页内容，自动提取正文。当 web_search 的摘要不够，需要查看某个具体页面的完整内容时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "要抓取的完整 URL，必须以 http:// 或 https:// 开头"
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "返回内容的最大字符数，超过会截断。默认 3000",
                        "default": 3000
                    }
                },
                "required": ["url"]
            }
        }
    }
]

# ===== 工具注册表 =====
REAL_TOOLS_REGISTRY = {
    "web_search": web_search,
    "fetch_url": fetch_url,
}

def execute_real_tool(tool_name: str, tool_args: dict) -> str:
    """统一的工具执行入口"""
    if tool_name not in REAL_TOOLS_REGISTRY:
        return f"错误：未知工具 '{tool_name}'"
    
    # ★ 新增：限流检查
    if not tracker.record(tool_name):
        return f"错误：工具 '{tool_name}' 调用次数已达本次会话上限，请总结现有信息回答"

    try:
        func = REAL_TOOLS_REGISTRY[tool_name]
        return func(**tool_args)
    except Exception as e:
        return f"错误：工具 '{tool_name}' 执行失败 - {type(e).__name__}: {e}"