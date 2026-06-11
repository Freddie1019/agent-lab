"""
任务1：理解 tokenizer 和中英文 token 差异
"""
from nntplib import decode_header
from uu import decode
import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o-mini")

def show_tokens(text: str):
    tokens = enc.encode(text)
    decoded = [enc.decode([t]) for t in tokens]
    print(f"\n文本： {text!r}")
    print(f"  字符数: {len(text)}")
    print(f"  Token 数: {len(tokens)}")
    print(f"  Token IDs: {tokens[:10]}{'...' if len(tokens) > 10 else ''}")
    print(f"  切分结果: {decoded[:15]}")


# ===== 实验 1：中英文对比 =====
# show_tokens("Hello world")
# show_tokens("你好世界")
# show_tokens("Hello, world! How are you doing today?")
# show_tokens("你好，世界！你今天过得怎么样？")

# # ===== 实验 2：代码 vs 自然语言 =====
# show_tokens("def calculate_sum(a, b): return a + b")
# show_tokens("定义一个函数，接收 a 和 b，返回它们的和")

# # ===== 实验 3：罕见字符 =====
# show_tokens("emoji 测试 🎉🚀")
# show_tokens("生僻字：彧 龘 麤")  # 体感会很差

# # ===== 实验 4：相同语义不同表达 =====
# show_tokens("OK")
# show_tokens("好的")
# show_tokens("行")  # 体感最短

test_text = """在当今的计算机科学与人工智能领域，AI Agent（人工智能智能体）无疑是最具颠覆性的核心概念之一。
简单来说，An Agent is an autonomous entity that can perceive its environment, make decisions, and take actions to achieve specific goals.
（智能体是一个能够感知环境、做出决策并采取行动以实现特定目标的自主实体）。不同于传统的软件程序，一个成熟的 AI Agent 通常包含四个核心支柱（Four Core Pillars）：
Perception（感知）：Through text, images, or audio inputs, the Agent senses the state of its current environment.（通过文本、图像或音频等输入，智能体感知其当前环境的状态）。
Brain / LLM（大脑/大语言模型）：The Large Language Model acts as the central router and decision-maker, handling reasoning and planning.（大语言模型作为核心路由器和决策者，负责推理和规划）。
Memory（记忆）：Divided into short-term memory (in-context learning) and long-term memory (vector databases / RAG), allowing the Agent to retain historical information.
（分为短期记忆和长期记忆，使智能体能够保留历史信息）。Tools Execution（工具执行）：Agents can leverage external APIs, calculator tools, or code interpreters to extend their capabilities beyond pure text generation.
（智能体可以利用外部 API、计算器工具或代码解释器来扩展其超越纯文本生成的能力）。
The Shift in Paradigm: 传统软件是基于固定逻辑的（If-Then rules），而 AI Agent 则是基于目标的（Goal-driven）。
You just give it a high-level task, and the Agent will figure out the "how" by iterating through the ReAct (Reason + Act) loop.
随着技术的演进，我们正从 Single-Agent 系统走向 Multi-Agent Systems (MAS，多智能体系统)。
In a Multi-Agent environment, different Agents are assigned distinct roles (like a product manager, a coder, and a tester). 
They collaborate, debate, and review each other's work to minimize hallucinations (减少幻觉) and solve highly complex, enterprise-level tasks. 
From automated software engineering to autonomous scientific discovery, AI Agents are redefining the future of human-AI collaboration.
"""
def compare_model(long_text: str, model: str):
    enc = tiktoken.encoding_for_model(model)
    tokens = enc.encode(long_text)
    decoded = [enc.decode([t]) for t in tokens]
    print(f"\n{'='*60}")
    print(model)
    print(f"\n文本： {long_text!r}")
    print(f"  字符数: {len(long_text)}")
    print(f"  Token 数: {len(tokens)}")
    print(f"  Token IDs: {tokens[:10]}{'...' if len(tokens) > 10 else ''}")
    print(f"  切分结果: {decoded[:15]}")

# # ===== gpt-4o-mini =====
compare_model(test_text,"gpt-4o-mini")

# # ===== gpt-3.5-turbo =====
compare_model(test_text,"gpt-3.5-turbo")

# # ===== text-embedding-3-small =====
compare_model(test_text,"text-embedding-3-small")