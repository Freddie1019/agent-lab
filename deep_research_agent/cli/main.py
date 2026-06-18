"""
Deep Research Agent CLI
用法：
  uv run python -m deep_research_agent.cli.main "你的问题"
  uv run python -m deep_research_agent.cli.main "你的问题" --steps 15 --budget 100000
"""
import sys
import argparse
import json
from pathlib import Path

from deep_research_agent.core.agent import ResearchAgent

def main():
    parser = argparse.ArgumentParser(
        description="Deep Research Agent - 一个能自主搜索互联网的研究助手",
    )
    parser.add_argument(
        "question",
        type=str,
        help="你的研究问题"
    )
    parser.add_argument(
        "--steps",
        type=int,
        default=10,
        help="最大执行步数（默认 10）",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=50_000,
        help="Token 预算上限（默认 50000）",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="使用的 LLM 模型",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="只输出最终答案",
    )
    parser.add_argument(
        "--save-report",
        type=str,
        default=None,
        help="把运行报告保存到指定 JSON 文件",
    )

    args = parser.parse_args()

    agent = ResearchAgent(
        model=args.model,
        max_steps=args.steps,
        max_tokens_budget=args.budget,
        verbose=not args.quiet,
    )

    report = agent.run(args.question)

    if not args.quiet:
        report.print_summary()
    
    print(f"\n{'─' * 70}")
    print("📝 最终回答")
    print(f"{'─' * 70}")
    print(report.final_answer or "（未能完成研究）")

    if args.save_report:
        path = Path(args.save_report)
        path.write_text(
            json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n📄 完整报告已保存到: {path}")
    
    # 失败时返回非零退出码
    return 0 if report.status == "success" else 1


if __name__ == "__main__":
    sys.exit(main())