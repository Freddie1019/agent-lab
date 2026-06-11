"""
任务1：观察 LLM 的工具调用请求长什么样
不实际执行工具，只是看 LLM 返回的 tool_calls 结构
"""
import os
import json
from random import choice
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url=os.getenv("MOONSHOT_BASE_KEY"),
)

# 定义一个工具（先不实现具体函数，只声明给 LLM 看）
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称，例如 'Paris', '北京'"
                    }
                },
                "required": ["city"]
            }
        }
    }
]

def ask(user_message):
    """对比：带工具 vs 不带工具的回答"""
    response = client.chat.completions.create(
        model="kimi-k2.6",
        messages=[{"role": "user", "content": user_message}],
        tools=tools,
        tool_choice="auto",
    )

    choice = response.choices[0]
    print(f"\n问题：{user_message}")
    print(f"finish_reason: {choice.finish_reason}")
    print(f"content: {choice.message.content}")

    if choice.message.tool_calls:
        print("→ LLM 请求调用工具：")
        for tc in choice.message.tool_calls:
            print(f"   工具名: {tc.function.name}")
            print(f"   参数(字符串): {tc.function.arguments}")
            print(f"   参数(解析后): {json.loads(tc.function.arguments)}")
            print(f"   调用 ID: {tc.id}")
    else:
        print("→ LLM 没有调用工具，直接回答了")

# 实验 1：明显需要工具的问题
ask("巴黎现在天气怎么样？")

# 实验 2：不需要工具的问题
ask("1 + 1 等于几？")

# 实验 3：参数模糊的情况
ask("天气怎么样？")  # 没说哪里