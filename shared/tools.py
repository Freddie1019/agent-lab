"""
可复用工具集合
每个工具是一个普通 Python 函数 + 一段 schema 描述
"""

from datetime import datetime

# ===== 工具实现 =====
def get_weather(city: str) -> str:
    """模拟天气查询"""
    fake_data = {
        "Paris": "22°C 晴朗",
        "巴黎": "22°C 晴朗",
        "北京": "15°C 多云",
        "Beijing": "15°C 多云",
        "Tokyo": "18°C 小雨",
        "东京": "18°C 小雨",
        "New York": "10°C 大风",
        "纽约": "10°C 大风",
    }
    return fake_data.get(city, f"暂无 {city} 的天气数据")

def calculator(expression: str) -> str:
    """安全计算器"""
    try:
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "错误：表达式包含非法字符"
        result = eval(expression)
        return f"{expression} = {result}"
    except Exception as e:
        return f"计算错误：{e}"

def get_current_time() -> str:
    """获取当前时间"""
    return f"当前时间是 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

# ===== 工具映射表（名字 → 函数） =====
TOOL_REGISTRY = {
    "get_weather": get_weather,
    "calculator": calculator,
    "get_current_time": get_current_time,
}

# ===== 工具 Schema（喂给 LLM 看的"说明书"） =====
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "查询指定城市的当前天气情况，返回温度和天气状况",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名，支持中英文，如 'Paris', '北京'"
                    }
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "数学表达式求值，支持加减乘除和括号。当需要做任何数学运算时使用此工具，不要自己心算。",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {
                        "type": "string",
                        "description": "数学表达式，如 '22 - 15', '(100 + 200) * 0.8'"
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
            "description": "获取当前的系统日期和时间",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

def execute_tool(tool_name: str, tool_args: dict) -> str:
    """
    工具执行的统一入口
    包含基础的错误处理：未知工具、执行异常
    """
    if tool_name not in TOOL_REGISTRY:
        return f"错误：未知工具 '{tool_name}'"
    
    try:
        func = TOOL_REGISTRY[tool_name]
        return func(**tool_args)
    except TypeError as e:
        return f"错误：工具 '{tool_name}' 参数不正确 - {e}"
    except Exception as e:
        return f"错误：工具 '{tool_name}' 执行失败 - {e}"