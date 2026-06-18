"""Demo 4: HITL 机制（使用文件工具，会触发红色权限）"""
import sys,os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from shared.llm_client import client, DEFAULT_MODEL
from shared.dangerous_tools import DANGEROUS_TOOLS, DANGEROUS_TOOLS_SCHEMA
from shared.safety import safe_execute
from shared.agent_errors import AgentError, classify_exception
import json

# 创建测试文件
os.makedirs("/tmp/agent_sandbox", exist_ok=True)
with open("/tmp/agent_sandbox/temp.log", "w") as f:
    f.write("可以删除的临时日志")

# 简化版（直接使用 shared，不走 ResearchAgent，因为后者只配了搜索工具）
SYSTEM_PROMPT = "你是文件管理助手。沙箱在 /tmp/agent_sandbox/"

messages = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": "请删除沙箱里的 temp.log 文件"},
]

for step in range(5):
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=messages,
        tools=DANGEROUS_TOOLS_SCHEMA,
        temperature=0,
    )
    msg = response.choices[0].message
    messages.append(msg)
    
    if msg.content:
        print(f"💭 {msg.content}")
    
    if response.choices[0].finish_reason == "stop":
        print(f"✅ {msg.content}")
        break
    
    if response.choices[0].finish_reason == "tool_calls":
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            tool_args = json.loads(tc.function.arguments)
            metadata = DANGEROUS_TOOLS[tool_name]
            print(f"🔧 [{metadata.danger_level.value.upper()}] {tool_name}({tool_args})")
            try:
                result = safe_execute(metadata, tool_args)
            except AgentError as e:
                result = e.to_llm_message()
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": str(result),
            })