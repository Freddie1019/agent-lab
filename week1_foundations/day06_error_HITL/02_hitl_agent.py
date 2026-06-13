"""
带 HITL 机制的文件系统 Agent
让 Agent 真的能读写文件，红色工具需要人工确认
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.llm_client import client, DEFAULT_MODEL
from shared.safety import safe_execute
from shared.dangerous_tools import DANGEROUS_TOOLS, DANGEROUS_TOOLS_SCHEMA
from shared.agent_errors import AgentError, classify_exception


SYSTEM_PROMPT = """你是一个文件系统助手，能列出、读取、写入、删除文件。

工作原则：
1. 删除操作不可逆，调用前必须明确告诉用户你要删什么文件、为什么
2. 写入操作会覆盖已有文件，操作前先列目录看看
3. 每次操作前用一句话说出你的计划

工作沙箱：/tmp/agent_sandbox/
"""


def run_file_agent(user_question: str, max_steps: int = 10):
    print(f"\n{'='*70}")
    print(f"用户任务: {user_question}")
    print(f"{'='*70}\n")
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_question}
    ]
    
    for step in range(1, max_steps + 1):
        print(f"━━━ 第 {step} 步 ━━━")
        
        response = client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=messages,
            tools=DANGEROUS_TOOLS_SCHEMA,
            temperature=0,
        )
        
        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        messages.append(msg)
        
        if msg.content:
            print(f"💭 {msg.content}")
        
        if finish_reason == "stop":
            print(f"\n✅ 任务完成\n")
            return msg.content
        
        if finish_reason == "tool_calls":
            for tc in msg.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)
                
                # 找到工具元数据
                if tool_name not in DANGEROUS_TOOLS:
                    result = f"未知工具: {tool_name}"
                else:
                    metadata = DANGEROUS_TOOLS[tool_name]
                    print(f"🔧 [{metadata.danger_level.value.upper()}] {tool_name}({tool_args})")
                    
                    # ★ 关键：通过 safe_execute 包装
                    try:
                        result = safe_execute(
                            metadata=metadata,
                            tool_args=tool_args,
                            agent_reasoning=msg.content or "",
                        )
                    except AgentError as e:
                        result = e.to_llm_message()
                    except Exception as e:
                        result = classify_exception(e).to_llm_message()
                
                print(f"📋 结果: {str(result)[:200]}")
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": str(result),
                })
            continue
        
        print(f"⚠️ 异常 finish_reason: {finish_reason}")
        return None
    
    return None


if __name__ == "__main__":
    # 准备测试文件
    sandbox = "/tmp/agent_sandbox"
    os.makedirs(sandbox, exist_ok=True)
    with open(f"{sandbox}/important.txt", "w", encoding="utf-8") as f:
        f.write("重要数据，不能删！")
    with open(f"{sandbox}/temp.log", "w", encoding="utf-8") as f:
        f.write("临时日志，可以删除")
    with open(f"{sandbox}/readme.md", "w", encoding="utf-8") as f:
        f.write("# 项目说明\n这是测试沙箱")
    
    # # 测试 1：纯只读任务（应该全程不打扰用户）
    # run_file_agent("看看沙箱里有哪些文件，并读一下 readme.md 的内容")
    
    # # 测试 2：写文件（YELLOW，应该有审计日志但不打扰）
    # run_file_agent("在沙箱里创建一个 hello.txt，写入 'Hello HITL!'")
    
    # 测试 3：删除文件（RED，必须人工确认）
    run_file_agent("清理沙箱里所有 .log 后缀的临时文件")