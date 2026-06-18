"""
模拟"别人的程序"调用你的 Agent API
"""
import httpx
import time
API_URL = "http://127.0.0.1:8000/research"

def call_research(question: str):
    print(f"\n📤 发送请求: {question}")
    start = time.time()
    
    response = httpx.post(
        API_URL,
        json={"question": question, "max_steps": 5},
        timeout=240,  # ★ Agent 可能跑很久
    )
    
    elapsed = time.time() - start
    print(f"📥 响应耗时: {elapsed:.1f}s, 状态码: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"   状态: {data['status']}")
        print(f"   步数: {data['steps']}, 工具调用: {data['tool_calls']}")
        print(f"   成本: ${data['estimated_cost_usd']:.4f}")
        print(f"\n回答:\n{data['answer']}")
    else:
        print(f"   错误: {response.text}")


if __name__ == "__main__":
    call_research("介绍下meta公司？")

