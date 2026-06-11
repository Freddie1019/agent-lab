"""
任务2：最简版 ReAct Agent
只有循环 + 工具执行，先把骨架跑通
"""
import json
import sys
import os

from openai.types.beta import assistant

# 让 Python 找到上两层的 shared 目录
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.llm_client import client, DEFAULT_MODEL
from shared.tools import TOOLS_SCHEMA, execute_tool

def run_agent(user_question: str, max_steps: int=10):
    """
    一个最简单的 ReAct Agent
    - 循环调用 LLM
    - LLM 想调工具就执行，结果塞回 messages
    - LLM 不想调工具了（finish_reason="stop"）就退出
    - max_steps 防止死循环
    """
    print(f"\n{'='*60}")
    print(f"用户问题：{user_question}")
    print(f"{'='*60}\n")

    messages = [
        {
            "role": "system",
            "content": "你是一个智能助手。当遇到需要外部信息（天气、时间）或精确计算的问题时，必须使用提供的工具。不要自己编造数据或心算。"
        },
        {"role": "user", "content": user_question}
    ]

    for step in range(1, max_steps + 1):
        print(f"--- 第 {step} 步 ---")

        # 调用 LLM
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            tools=TOOLS_SCHEMA,
        )

        assistant_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        messages.append(assistant_message)

        # 情况 1：LLM 完事了，输出最终答案
        if finish_reason == 'stop':
            print(f"\n✅ Agent 给出最终答案（共 {step} 步）：")
            print(f"   {assistant_message.content}\n")
            return assistant_message.content
        
        # 情况 2：LLM 想调工具
        if finish_reason == "tool_calls":
            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                print(f"  🔧 调用 {tool_name}({tool_args})")
                result = execute_tool(tool_name, tool_args)
                print(f"  📋 结果：{result}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                })
            continue

        # 情况 3：其他（比如 length、content_filter）
        print(f"⚠️ 异常终止：finish_reason={finish_reason}")
        return None

    # 走到这里说明超过 max_steps
    print(f"⚠️ 达到最大步数 {max_steps}，强制终止")
    return None

if __name__ == "__main__":
    # 测试 1：单步任务
    run_agent("现在几点了？")

    # 测试 2：两步任务
    run_agent("巴黎天气怎么样？")  # 1 步：调工具，2 步：回答

    # 测试 3：多步任务（关键！）
    run_agent("巴黎和北京哪个城市现在更暖和？温差是多少度？")

    # 测试 4：不需要工具的任务
    run_agent("ReAct 这个词是什么意思？")