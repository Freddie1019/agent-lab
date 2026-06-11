"""
压力测试：证明上下文管理真的 work
对比 sliding_window vs summarization 两种策略
验证 4 个断言：
  1. token 数始终受控（不超 max_tokens + 10%）
  2. 关键信息召回（摘要应该能记住，滑窗应该忘记）
  3. 总成本 < $0.10
  4. 可视化三条 token 曲线（无压缩 / 滑窗 / 摘要）
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from longevous_agent import LongevousChatAgent
from shared.token_counter import count_messages_tokens


# ===== 价格表（gpt-4o-mini，单位 $/M tokens）=====
PRICE_INPUT = 0.15
PRICE_OUTPUT = 0.60


def calculate_cost(stats: dict) -> float:
    """根据 stats 估算总成本"""
    input_cost = stats["total_input_tokens"] * PRICE_INPUT / 1_000_000
    output_cost = stats["total_output_tokens"] * PRICE_OUTPUT / 1_000_000
    return input_cost + output_cost


def check_recall(answer: str, keyword: str = "XYZ") -> bool:
    """程序化判断召回是否成功（关键词出现 = 召回成功）"""
    return keyword.lower() in answer.lower()


def stress_test(strategy: str, n_turns: int = 100, max_tokens: int = 2000):
    print(f"\n{'='*60}")
    print(f"开始压力测试：strategy={strategy}, n_turns={n_turns}")
    print(f"{'='*60}")

    agent = LongevousChatAgent(strategy=strategy, max_tokens=max_tokens)

    # ===== 第 1 轮埋关键信息 =====
    agent.chat("请记住一个重要事实：我叫小明，我在 XYZ 公司工作。")

    token_history = []
    compression_points = []  # 记录哪些轮次触发了压缩
    last_compression_count = 0

    # ===== 中间灌闲聊 =====
    topics = [
        "今天天气真不错", "你喜欢什么颜色", "推荐一部电影", "Python 怎么学",
        "周末去哪玩", "怎么减肥", "睡眠不好怎么办", "学英语的方法",
        "投资理财建议", "怎么提升专注力",
    ]

    for i in range(2, n_turns):
        topic = topics[i % len(topics)]
        agent.chat(f"第{i}轮闲聊：{topic}")

        stats = agent.stats()
        current_tokens = stats["current_context_tokens"]
        token_history.append(current_tokens)

        # 记录压缩事件
        if stats["compression_count"] > last_compression_count:
            compression_points.append(i)
            last_compression_count = stats["compression_count"]

        # ★ 断言 1：token 不能爆（容忍 10% buffer）
        token_limit = max_tokens * 1.1
        assert current_tokens <= token_limit, \
            f"第{i}轮 token 爆了！{current_tokens} > {token_limit}"

        # 每 10 轮打印进度
        if i % 10 == 0:
            print(f"  [第{i:3d}轮] context_tokens={current_tokens:4d}, 累计压缩{stats['compression_count']}次")

    # ===== 最后召回测试 =====
    # 在召回测试前加这两行
    print("\n=== 召回测试前的完整 messages ===")
    for i, m in enumerate(agent.messages):
        role = m["role"] if isinstance(m, dict) else m.role
        content = m.get("content") if isinstance(m, dict) else m.content
        if content:
            print(f"[{i}] [{role}] {content[:150]}{'...' if len(content) > 150 else ''}")
    print("=" * 60)
    
    print(f"\n  [召回测试] 问：'我在哪家公司？'")
    recall_answer = agent.chat("我在哪家公司工作？请直接说出公司名。")
    print(f"  Agent 回答：{recall_answer}")
    recall_success = check_recall(recall_answer, "XYZ")
    print(f"  → 召回{'成功 ✅' if recall_success else '失败 ❌'}")

    # ===== 成本统计 =====
    final_stats = agent.stats()
    cost = calculate_cost(final_stats)

    print(f"\n  最终统计:")
    print(f"    总轮次: {final_stats['turn']}")
    print(f"    压缩次数: {final_stats['compression_count']}")
    print(f"    Input tokens 累计: {final_stats['total_input_tokens']}")
    print(f"    Output tokens 累计: {final_stats['total_output_tokens']}")
    print(f"    总成本: ${cost:.4f}")

    # ★ 断言 3：成本上限
    assert cost < 0.10, f"成本超标！${cost:.4f} > $0.10"

    return {
        "strategy": strategy,
        "token_history": token_history,
        "compression_points": compression_points,
        "recall_success": recall_success,
        "cost": cost,
        "stats": final_stats,
    }


def simulate_no_compression(n_turns: int = 100) -> list:
    """
    模拟"不做任何压缩"的对照组——只算 token 数，不真调 LLM（省钱）
    """
    from shared.llm_client import DEFAULT_MODEL
    messages = [{"role": "system", "content": "你是助手"}]
    messages.append({"role": "user", "content": "请记住一个重要事实：我叫小明，我在 XYZ 公司工作。"})
    messages.append({"role": "assistant", "content": "好的，我记住了小明在 XYZ 公司工作。"})

    history = []
    topics = ["今天天气", "你喜欢什么颜色", "推荐电影", "学 Python"]
    for i in range(2, n_turns):
        messages.append({"role": "user", "content": f"第{i}轮闲聊：{topics[i % len(topics)]}"})
        messages.append({"role": "assistant", "content": f"关于{topics[i % len(topics)]}，我的看法是这样...." * 3})
        history.append(count_messages_tokens(messages, DEFAULT_MODEL))
    return history


def plot_ascii(results: list, no_compression: list):
    """ASCII 简易可视化（也可以改成 matplotlib）"""
    print("\n" + "="*60)
    print("Token 曲线对比（每 10 轮采样一次）")
    print("="*60)
    print(f"{'轮次':>6} | {'无压缩':>10} | {'滑窗':>10} | {'摘要':>10}")
    print("-" * 50)
    
    sliding = next((r["token_history"] for r in results if r["strategy"] == "sliding_window"), [])
    summary = next((r["token_history"] for r in results if r["strategy"] == "summarization"), [])

    n = min(len(no_compression), len(sliding), len(summary))
    for i in range(0, n, 10):
        nc = no_compression[i] if i < len(no_compression) else 0
        sl = sliding[i] if i < len(sliding) else 0
        sm = summary[i] if i < len(summary) else 0
        bar_nc = "█" * min(nc // 200, 40)
        print(f"{i+2:>6} | {nc:>10} | {sl:>10} | {sm:>10}  {bar_nc}")


if __name__ == "__main__":
    print("\n>>> 模拟「无压缩」对照组（不调 LLM，只算 token）")
    no_compression_history = simulate_no_compression(n_turns=100)
    print(f"  100 轮后 token 数：{no_compression_history[-1]}（如果真的发 LLM，单轮就会超模型上限）")

    # ★ A/B 对比
    print("\n>>> 正式压力测试")
    results = []
    for strategy in ["sliding_window", "summarization"]:
        result = stress_test(strategy, n_turns=100, max_tokens=5000)
        results.append(result)

    # ★ 可视化
    plot_ascii(results, no_compression_history)

    # ★ 汇总
    print("\n" + "="*60)
    print("最终对比")
    print("="*60)
    print(f"{'策略':<20} | {'召回':<10} | {'压缩次数':<10} | {'总成本':<10}")
    print("-" * 60)
    for r in results:
        print(f"{r['strategy']:<20} | {'✅' if r['recall_success'] else '❌':<10} | {r['stats']['compression_count']:<10} | ${r['cost']:.4f}")

    # ★ 断言 2：召回行为符合预期
    sliding_result = next(r for r in results if r["strategy"] == "sliding_window")
    summary_result = next(r for r in results if r["strategy"] == "summarization")

    print("\n断言 2 验证（召回行为）：")
    if not sliding_result["recall_success"]:
        print("  ✅ 滑窗忘记了 XYZ —— 符合预期")
    else:
        print("  ⚠️ 滑窗居然记住了？可能 max_tokens 设太大、压缩没真触发")

    if summary_result["recall_success"]:
        print("  ✅ 摘要记住了 XYZ —— 符合预期")
    else:
        print("  ⚠️ 摘要没记住，可能摘要 prompt 不够好（开放讨论题正好用上）")

    print("\n🎉 压力测试完成！")