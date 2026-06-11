"""
任务3：让 Agent 的"思考过程"可见
通过修改 system prompt，让 LLM 在调用工具前先输出 Thought
"""
from email import message
import json
import sys
import os

from openai import responses
# 让 Python 找到上两层的 shared 目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.llm_client import client, DEFAULT_MODEL
from shared.tools import TOOLS_SCHEMA, execute_tool

# ★ 关键改动：在 system prompt 里要求 LLM 先思考
REACT_SYSTEM_PROMPT = """你是一个智能任务助手，采用 ReAct（Reasoning + Acting）模式工作。

工作规则：
1. 每次决定调用工具前，先用一段简短的中文说出你的思考（思考当前已知什么、还缺什么、下一步该做什么）
2. 思考后再调用工具
3. 多个独立任务可以一次性并行调用多个工具
4. 拿到所有信息后给出最终回答

可用工具：
- get_weather(city): 查询城市天气
- calculator(expression): 数学计算
- get_current_time(): 获取当前时间

记住：涉及实时信息或计算时必须用工具，不要凭印象或心算。
"""

def run_agent(user_question: str, max_steps: int=10):
    print(f"\n{'='*60}")
    print(f"用户问题：{user_question}")
    print(f"{'='*60}\n")

    messages =[
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": user_question}
    ]

    for step in range(1, max_steps + 1):
        print(f"━━━ 第 {step} 步 ━━━")

        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
        )

        assistant_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        messages.append(assistant_message)

        # ★ 关键改动：如果 LLM 输出了 content（思考过程），打印出来
        if assistant_message.content:
            print(f"💭 思考：{assistant_message.content}")

        if finish_reason == "stop":
            print(f"\n✅ 完成（共 {step} 步）\n")
            return assistant_message.content

        if finish_reason == "tool_calls":
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"🔧 行动：{tool_name}({tool_args})")
                result = execute_tool(tool_name, tool_args)
                print(f"📋 观察：{result}\n")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
            continue

        print(f"⚠️ 异常：{finish_reason}")
        return None

    print(f"⚠️ 达到最大步数 {max_steps}")
    return None

if __name__ == "__main__":
    # 经典的多步任务：观察思考过程
    run_agent("巴黎和北京哪个城市现在更暖和？温差是多少度？")

    print("\n" + "="*60)

    # 更复杂的：3 个城市排序
    run_agent("巴黎、北京、东京三个城市，从冷到热排序，并算出最高温和最低温的差")