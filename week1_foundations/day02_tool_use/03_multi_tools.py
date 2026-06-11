"""
任务3：多个工具，LLM 自主选择该用哪个
"""
import os
import json 
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI(
    api_key=os.getenv("MOONSHOT_API_KEY"),
    base_url=os.getenv("MOONSHOT_BASE_KEY"),
)

# ===== 三个工具 =====
def get_weather(city: str) -> str:
    fake_data = {"Paris": "22°C 晴", "北京": "15°C 多云", "Tokyo": "18°C 小雨"}
    return fake_data.get(city, f"暂无 {city} 数据")

def calculator(expression: str) -> str:
    """安全的表达式求值"""
    try:
        # 仅允许数字和基本运算符（生产环境要更严格）
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "错误：包含非法字符"
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误：{e}"
    
def get_current_time(timezone: str = "Asia/Shanghai") -> str:
    """获取当前时间（简化版，先不处理真实时区）"""
    return f"当前时间是 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ({timezone})"

AVAILABLE_TOOLS = {
    "get_weather": get_weather,
    "calculator": calculator,
    "get_current_time": get_current_time,
}

# ===== 工具 Schema =====
tools_schema = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气情况",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "对一个数学表达式求值。支持加减乘除和括号。当用户问数学题时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '2 + 3 * 4'"
                    }
                },
                "required": ["expression"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "获取当前的日期和时间",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "时区名，如 'Asia/Shanghai'。默认上海时区"
                    }
                },
                "required": []
            }
        }
    }
]

# ===== 复用 task2 的主流程 =====
def chat_with_tools(user_message: str):
    print(f"\n{'='*60}")
    print(f"问：{user_message}")

    messages = [{"role": "user", "content": user_message}]

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
    
    print(f"LLM 选择调用：", end="")
    for tc in assistant_message.tool_calls:
        print(f"{tc.function.name}({tc.function.arguments})", end=" ")
    print()

    for tool_call in assistant_message.tool_calls:
        tool_name = tool_call.function.name
        tool_args = json.loads(tool_call.function.arguments)
        result = AVAILABLE_TOOLS[tool_name](**tool_args)
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": result
        })
    
    final = client.chat.completions.create(
        model="kimi-k2.6",
        messages=messages,
        tools=tools_schema,
    )

    print(f"答：{final.choices[0].message.content}")

if __name__ == "__main__":
    # 让 LLM 自己选择该用哪个工具
    chat_with_tools("北京今天什么天气？")        # 应该用 get_weather
    chat_with_tools("帮我算 (123 + 456) * 2")   # 应该用 calculator
    chat_with_tools("现在几点了？")              # 应该用 get_current_time
    chat_with_tools("你是谁？")                  # 不用工具