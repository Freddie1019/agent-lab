"""测试两个真实工具能不能跑通"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.real_tools import web_search, fetch_url

print("=== 测试 web_search ===")
result = web_search("Anthropic Claude 4 发布时间", max_results=3)
print(result[:1500])

print("\n\n=== 测试 fetch_url ===")
# 用一个已知能抓的页面
result = fetch_url("https://en.wikipedia.org/wiki/Large_language_model", max_chars=1000)
print(result)

print("\n\n=== 测试错误处理 ===")
# 故意用一个不存在的 URL
result = fetch_url("https://this-domain-does-not-exist-xyz.com")
print(result)