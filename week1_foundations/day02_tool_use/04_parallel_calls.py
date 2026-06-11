"""
任务4：观察并行工具调用
当用户问题需要多个工具时，LLM 会一次返回多个 tool_calls
"""
import os
import json
import time
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url=os.getenv("MOONSHOT_BASE_KEY"),
)

def get_weather(city: str) -> str:
    # 模拟 API 调用耗时
    time.sleep(1)
    fake = {"Paris": "22°C 晴", "Tokyo": "18°C 雨", "New York": "10°C 多云"}
    return fake.get(city, f"无 {city} 数据")

AVAILABLE_TOOLS = {"get_weather": get_weather}

tools_schema = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "查询单个城市的天气",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"]
        }
    }
}]

def chat_with_parallel_tools(user_message: str):
    print(f"\n问：{user_message}")
    messages = [{"role": "user", "content": user_message}]

    start = time.time()

    response = client.chat.completions.create(
        model="kimi-k2.6",
        messages=messages,
        tools=tools_schema,
    )

    assistant_message = response.choices[0].message
    messages.append(assistant_message)

    if not assistant_message.tool_calls:
        print(f"答：{assistant_message.content}")
        return

    print(f"LLM 一次返回了 {len(assistant_message.tool_calls)} 个工具调用：")

    # ⚠️ 这里我们是"顺序"执行的（每个 sleep 1秒，3 个就是 3 秒）
    # Week 4 会改成 asyncio 真正并发
    for tc in assistant_message.tool_calls:
        args = json.loads(tc.function.arguments)
        print(f"  调用 {tc.function.name}({args})...")
        result = AVAILABLE_TOOLS[tc.function.name](**args)
        print(f"  ← {result}")

        messages.append({
            "role": "tool",
            "tool_call_id": tc.id,
            "content": result
        })
        
    print(messages)

    final = client.chat.completions.create(
        model="kimi-k2.6",
        messages=messages,
        tools=tools_schema,
    )
    print(f"\n答：{final.choices[0].message.content}")
    print(f"总耗时：{time.time() - start:.2f}s")


if __name__ == "__main__":
    # 这个问题会触发 LLM 一次返回 3 个 tool_calls
    chat_with_parallel_tools("帮我查一下 Paris、Tokyo、New York 三个城市的天气，对比一下")