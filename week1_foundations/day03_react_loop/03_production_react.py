"""
任务4：生产级护栏版 ReAct Agent
加入：步数限制、token 统计、token 熔断、运行报告
"""
import json
import sys
import os
import time

from openai import responses
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.llm_client import client, DEFAULT_MODEL
from shared.tools import TOOLS_SCHEMA, execute_tool

REACT_SYSTEM_PROMPT = """你是一个智能任务助手，采用 ReAct 模式工作。

工作规则：
1. 调用工具前先用一句话说出你的思考
2. 多个独立任务可以并行调用工具
3. 拿到所有需要的信息后立即给出最终回答，不要做不必要的工具调用
4. 涉及实时信息或计算时必须用工具

可用工具：
- get_weather(city): 查询城市天气
- calculator(expression): 数学计算
- get_current_time(): 获取当前时间

记住：涉及实时信息或计算时必须用工具，不要凭印象或心算。
"""

class AgentRunReport:
    """运行报告：记录 Agent 一次执行的全部统计信息"""
    def __init__(self):
        self.steps = 0
        self.tool_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.start_time = time.time()
        self.status = "running"  # running / completed / max_steps / token_limit / error
        self.final_answer = None
    
    @property
    def total_tokens(self):
        return self.total_input_tokens + self.total_output_tokens
    
    @property
    def elapsed(self):
        return time.time() - self.start_time
    
    def print_summary(self):
        print("\n" + "─" * 60)
        print(f"📊 运行报告")
        print(f"   状态: {self.status}")
        print(f"   步数: {self.steps}")
        print(f"   工具调用次数: {self.tool_calls}")
        print(f"   Token 用量: input={self.total_input_tokens}, output={self.total_output_tokens}, 总计={self.total_tokens}")
        print(f"   耗时: {self.elapsed:.2f}s")
        # gpt-4o-mini 价格：input $0.15/1M tokens, output $0.6/1M tokens
        cost = self.total_input_tokens * 0.15 / 1_000_000 + self.total_output_tokens * 0.6 / 1_000_000
        print(f"   预估成本: ${cost:.6f}")
        print("─" * 60)
    
def run_agent(
    user_question: str,
    max_steps: int = 10,
    max_tokens_budget: int = 50_000,
):
    """
    生产级 ReAct Agent
    """
    print(f"\n{'='*60}")
    print(f"用户问题：{user_question}")
    print(f"配置：max_steps={max_steps}, token预算={max_tokens_budget}")
    print(f"{'='*60}\n")

    messages = [
        {"role": "system", "content": REACT_SYSTEM_PROMPT},
        {"role": "user", "content": user_question}
    ]

    report = AgentRunReport()

    for step in range(1, max_steps + 1):
        report.steps = step
        print(f"━━━ 第 {step} 步 ━━━")

        # ★ 护栏 1：token 熔断
        if report.total_tokens >= max_tokens_budget:
            print(f"⛔ Token 预算耗尽 ({report.total_tokens}/{max_tokens_budget})，终止")
            report.status = "token_limit"
            report.print_summary()
            return None
        
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=TOOLS_SCHEMA,
            )
        except Exception as e:
            print(f"⛔ LLM 调用失败: {e}")
            report.status = "error"
            report.print_summary()
            return None
        
        # ★ 统计 token
        report.total_input_tokens += response.usage.prompt_tokens
        report.total_output_tokens += response.usage.completion_tokens

        assistant_message = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        messages.append(assistant_message)

        if assistant_message.content:
            print(f"💭 思考：{assistant_message.content}")

        # 正常结束
        if finish_reason == "stop":
            print(f"\n✅ Agent 完成任务")
            print(f"   {assistant_message.content}")
            report.status = "completed"
            report.final_answer = assistant_message.content
            report.print_summary()
            return assistant_message.content
        
        # 调工具
        if finish_reason == "tool_calls":
            for tool_call in assistant_message.tool_calls:
                report.tool_calls += 1
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

        # 其他异常情况
        print(f"⚠️ 异常 finish_reason: {finish_reason}")
        report.status = "error"
        report.print_summary()
        return None

    # ★ 护栏 2：步数耗尽
    print(f"⛔ 达到最大步数 {max_steps}，强制终止")
    report.status = "max_steps"
    report.print_summary()
    return None    

if __name__ == "__main__":
    # 正常任务：观察护栏不触发时的报告
    run_agent("巴黎、北京、东京三个城市从冷到热排序，并算出最大温差")

    print("\n\n" + "█" * 60 + "\n\n")

    # 测试 max_steps 护栏：故意把步数限制设得很小
    run_agent(
        "巴黎、北京、东京、纽约四个城市的天气，并算出两两温差",
        max_steps=3  # 故意调小，看会不会被中断
    )