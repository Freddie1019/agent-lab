"""
混沌测试：30% 故障率下，研究 Agent 还能正常工作吗？
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.llm_client import client, DEFAULT_MODEL
from shared.real_tools import REAL_TOOLS_SCHEMA, REAL_TOOLS_REGISTRY
from shared.fault_injector import FaultInjector
from shared.agent_errors import AgentError, classify_exception

# ★ 用故障注入器包装真实工具
injector = FaultInjector(
    timeout_rate=0.15,
    rate_limit_rate=0.10,
    unavailable_rate=0.10,
    garbage_rate=0.05,
    enabled=True,
)

# 把工具替换成"会随机失败"的版本
chaotic_tools = {
    name: injector.wrap(func)
    for name, func in REAL_TOOLS_REGISTRY.items()
}

def execute_chaotic_tool(tool_name, tool_args):
    if tool_name not in chaotic_tools:
        return f"未知工具：{tool_name}"
    try:
        return chaotic_tools[tool_name](**tool_args)
    except AgentError as e:
        return e.to_llm_message()
    except Exception as e:
        return classify_exception(e).to_llm_message()

SYSTEM_PROMPT = """你是研究型 Agent。工具调用可能因各种原因失败：
- 超时：可以换关键词重试，或换种方式查
- 限流：稍等再试，或先用已有信息组织答案
- 不可用：尝试其他工具或方法
- 返回乱码：说明数据质量差，应该换源重查

你的任务是即使在不可靠的环境下，也尽力给用户有用的答案。如果实在拿不到信息，诚实告知。
"""

# SYSTEM_PROMPT = """你是研究型 Agent。你的核心任务是深入研究用户的需求，并利用你拥有的工具获取准确、详实、高质量的信息。

# 在执行任务时，请遵循以下流程：
# 1. 拆解需求：理解用户问题的核心，规划清晰的信息检索路径。
# 2. 精准检索：使用最相关的关键词和最合适的工具进行查询。
# 3. 整合分析：对获取的数据进行筛选、对比和逻辑推理，剔除低价值信息。
# 4. 专业输出：将研究结果以条理清晰、结构严谨的方式呈现给用户，确保答案有据可查。

# 请始终保持严谨、客观的研究者态度，追求最高标准的信息准确性。"""

def run_chaotic_research(question: str, max_steps: int = 10):
    print(f"\n{'='*70}\n问题: {question}\n{'='*70}")
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    
    for step in range(1, max_steps + 1):
        print(f"━━━ 第 {step} 步 ━━━")
        
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            tools=REAL_TOOLS_SCHEMA,
            temperature=0,
        )
        
        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        messages.append(msg)
        
        if msg.content:
            print(f"💭 {msg.content[:200]}")
        
        if finish_reason == "stop":
            print(f"\n✅ 最终回答:\n{msg.content}\n")
            return {"success": True, "answer": msg.content, "steps": step}
        
        if finish_reason == "tool_calls":
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)
                print(f"🔧 {tool_name}({tool_args})")
                result = execute_chaotic_tool(tool_name, tool_args)
                print(f"📋 {result[:150]}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            continue
        
        return {"success": False, "reason": f"finish_reason={finish_reason}"}
    
    return {"success": False, "reason": "达到最大步数"}


if __name__ == "__main__":
    # 跑 5 次同样的问题，看在故障注入下的成功率
    question = "2025 年比较流行的开源 Agent 框架有哪些？列出 2-3 个。"
    
    results = []
    for i in range(5):
        print(f"\n\n████ 第 {i+1} 次运行 ████")
        injector.stats = {k: 0 for k in injector.stats}  # 重置统计
        result = run_chaotic_research(question, max_steps=8)
        results.append(result)
        injector.report()
        time.sleep(2)
    
    # 总结
    print(f"\n\n{'#'*70}")
    print("总体成功率统计")
    print(f"{'#'*70}")
    success = sum(1 for r in results if r["success"])
    print(f"成功: {success}/5 ({success/5*100:.0f}%)")
    avg_steps = sum(r.get("steps", 0) for r in results if r["success"]) / max(success, 1)
    print(f"成功用例平均步数: {avg_steps:.1f}")