"""
任务2：完整的工具调用闭环
1. LLM 请求调用工具
2. 我们真的执行函数
3. 把结果送回 LLM
4. LLM 给出最终自然语言回答
"""
import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url=os.getenv("MOONSHOT_BASE_KEY"),
)

# ===== 1. 真正实现工具函数 =====
def get_weather(city: str) -> str:
    """模拟的天气查询（实际项目里这里会调天气 API）"""
    fake_data = {
        "Paris": "22°C 晴朗",
        "巴黎": "22°C 晴朗",
        "北京": "15°C 多云",
        "Tokyo": "18°C 小雨",
        "东京": "18°C 小雨",
    }
    return fake_data.get(city, f"暂无 {city} 的天气数据")

# ===== 2. 工具映射表（让我们能根据名字找到函数） =====
AVAILABLE_TOOLS = {
    "get_weather": get_weather,
}

# ===== 3. 工具的 JSON Schema 声明 =====
tools_schema = [
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

# ===== 4. 主流程 =====
def chat_with_tools(user_message: str):
    print(f"\n{'='*60}")
    print(f"用户问题：{user_message}")
    print(f"{'='*60}")

    messages = [
        {"role": "user", "content": user_message}
    ]

    # ----- 第 1 次调用 LLM -----
    print("\n[第 1 次调用 LLM]")
    response = client.chat.completions.create(
        model="kimi-k2.6",
        messages=messages,
        tools=tools_schema,
        tool_choice="auto",
    )

    assistant_message = response.choices[0].message
    print(f"finish_reason: {response.choices[0].finish_reason}")

    # 把 LLM 的回复（即使是 tool_calls）加入消息历史
    messages.append(assistant_message)

    # ----- 判断 LLM 是否要调用工具 -----
    if not assistant_message.tool_calls:
        # LLM 直接回答了，不需要工具
        print(f"LLM 直接回答了： {assistant_message.content}")
        return assistant_message.content
    
    # ----- 执行每一个工具调用 -----
    print(f"LLM 请求调用 {len(assistant_message.tool_calls)} 个工具：")

    for tool_call in assistant_message.tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)

        print(f"  → {tool_name}({tool_args})")

        # 查找并执行对应的 Python 函数
        if tool_name in AVAILABLE_TOOLS:
            tool_func = AVAILABLE_TOOLS[tool_name]
            tool_result = tool_func(**tool_args)
        else:
            tool_result = f"错误：未知工具 {tool_name}"

        print(f"  ← 结果：{tool_result}")

        # 把工具结果加入消息历史（用 role="tool"）
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": tool_result
        })

    # ----- 第 2 次调用 LLM（带上工具结果，让它组织最终回答） -----
    print("\n[第 2 次调用 LLM（带工具结果）]")
    final_response = client.chat.completions.create(
        model="kimi-k2.6",
        messages=messages,
        tools=tools_schema,
    )

    final_answer = final_response.choices[0].message.content
    print(f"\n最终回答：{final_answer}")

    # ----- 看一眼最终的 messages 数组结构 -----
    print(f"\n[最终 messages 数组共 {len(messages) + 1} 条消息]")
    for i, msg in enumerate(messages):
        role = msg["role"] if isinstance(msg, dict) else msg.role
        print(f"  {i}. role={role}")

    return final_answer

# ===== 5. 测试 =====
if __name__ == "__main__":
    chat_with_tools("巴黎天气怎么样？")
    chat_with_tools("1+1=?")  # 不需要工具的情况
