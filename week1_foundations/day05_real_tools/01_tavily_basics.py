"""
任务2：最简单的 Tavily 搜索调用
先理解 API 返回什么，再封装
"""
import os
import json
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

# ===== 最简单调用 =====
# 加参数
response = client.search(
    query="2025 年最值得学的开源 Agent 框架",
    search_depth="advanced",        # basic / advanced
    max_results=5,
    include_raw_content=True,        # ★ 关键参数：是否包含完整网页内容
    include_answer=True,             # ★ 让 Tavily 直接生成一个答案摘要
)

# 看一眼完整返回结构
print("=== 完整返回结构 ===")
print(json.dumps(response, ensure_ascii=False, indent=2)[:3000])

print(f"\n=== 返回了 {len(response['results'])} 条结果 ===")

# 关键字段
for i, r in enumerate(response['results'][:3], 1):
    print(f"\n--- 结果 {i} ---")
    print(f"标题: {r['title']}")
    print(f"URL:  {r['url']}")
    print(f"内容片段: {r['content'][:200]}...")
    print(f"分数: {r.get('score', 'N/A')}")