"""
任务4：研究型 Agent v1
- 复用 Day 3 的 ReAct 循环
- 工具换成真实的 web_search + fetch_url
- 加上昨天的 ContextManager（上下文管理）
"""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from shared.llm_client import client, DEFAULT_MODEL
from shared.real_tools import REAL_TOOLS_SCHEMA, execute_real_tool
from shared.context_manager import ContextManager
from shared.token_counter import count_messages_tokens
from shared.rate_limiter import tracker

# 设置本次会话上限
tracker.set_limit("web_search", 3)   # 单次研究最多 3 次搜索
tracker.set_limit("fetch_url", 3)    # 最多 3 次抓取

RESEARCH_SYSTEM_PROMPT = """你是一个严谨的研究型助手，采用 ReAct 模式工作。

工作原则：
1. 每次行动前先用一句话说出你的思考
2. 涉及最新信息、实时数据、不确定事实时，必须用 web_search 查证
3. 如果搜索摘要不够详细，用 fetch_url 抓取具体页面
4. 多个独立查询可以并行调用工具
5. 给出最终答案时，必须引用信息来源（URL）
6. 不要凭印象回答，不要编造未经验证的信息

可用工具：
- web_search(query, max_results): 搜索互联网
- fetch_url(url, max_chars): 抓取特定网页正文
"""
def run_research_agent(
    user_question: str,
    max_steps: int = 8,
    max_context_tokens: int = 8000,
):
    print(f"\n{'='*70}")
    print(f"研究问题：{user_question}")
    print(f"{'='*70}\n")

    messages = [
        {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
        {"role": "user", "content": user_question}
    ]

    cm = ContextManager(
        strategy="sliding_window",
        max_tokens=max_context_tokens,
        keep_recent_messages=8,
    )

    stats = {
        "steps": 0, "tool_calls": 0,
        "input_tokens": 0, "output_tokens": 0,
        "compressions": 0,
    }
    start = time.time()

    for step in range(1, max_steps + 1):
        stats["steps"] = step
        print(f"━━━ 第 {step} 步 ━━━")

        # 每步前检查上下文
        if cm.needs_compression(messages):
            before = count_messages_tokens(messages)
            messages = cm.compress(messages)
            after = count_messages_tokens(messages)
            stats["compressions"] += 1
            print(f"  [压缩] {before} → {after} tokens")
        
        try:
            response = client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=messages,
                tools=REAL_TOOLS_SCHEMA,
                temperature=0,
            )
        except Exception as e:
            print(f"⛔ LLM 调用失败: {e}")
            return None
        
        stats["input_tokens"] += response.usage.prompt_tokens
        stats["output_tokens"] += response.usage.completion_tokens

        msg = response.choices[0].message
        finish_reason = response.choices[0].finish_reason
        messages.append(msg)

        if msg.content:
            print(f"💭 {msg.content}")
        
        if finish_reason == "stop":
            print(f"\n✅ 完成（用时 {time.time()-start:.1f}s，{step} 步，"
                  f"{stats['tool_calls']} 次工具调用，"
                  f"总 token {stats['input_tokens']+stats['output_tokens']}）")
            print(f"\n{'─'*70}\n最终回答：\n{msg.content}\n")
            return msg.content
        
        if finish_reason == "tool_calls":
            for tc in msg.tool_calls:
                stats["tool_calls"] += 1
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)
                print(f"🔧 {tool_name}({tool_args})")
                
                tool_start = time.time()
                result = execute_real_tool(tool_name, tool_args)
                tool_elapsed = time.time() - tool_start
                
                # 显示结果摘要（前 200 字）
                preview = result[:200].replace("\n", " ")
                print(f"📋 [{tool_elapsed:.1f}s] {preview}...\n")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": result,
                })
            continue

        print(f"⚠️ 异常 finish_reason: {finish_reason}")
        return None

    print(f"⛔ 达到最大步数 {max_steps}")
    return None

if __name__ == "__main__":
    # 测试 1：需要查实时信息的问题
    run_research_agent(
    "请分别查询 OpenAI、Anthropic、Google、Meta、DeepSeek、xAI 这 6 家公司"
    "2025 年最新的旗舰模型名称和发布日期。"
    )
    tracker.report()
    