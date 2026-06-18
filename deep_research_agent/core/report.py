"""
运行报告：完整记录一次 Agent 执行的所有指标
"""
import time
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class RunReport:
    question: str
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None

    # 执行统计
    steps: int = 0
    tool_calls: int = 0
    compressions: int = 0
    hitl_triggers: int = 0

    # token与成本
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # 工具调用细节
    tool_call_details: list = field(default_factory=list)

    # 错误记录
    errors: list = field(default_factory=list)

    # 最终状态
    status: str = "running" # running / success / max_steps / token_limit / error
    final_answer: Optional[str] = None

    @property
    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time 
    
    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens
    
    @property
    def estimated_cost_usd(self) -> float:
        # gpt-4o-mini 价格
        return (self.total_input_tokens * 0.15 / 1_000_000 + 
                self.total_output_tokens * 0.60 / 1_000_000)
        
    def add_to_call(self, tool_name: str, args: dict, duration_ms: float, success: bool, result_preview: str = ""):
        self.tool_calls += 1
        self.tool_call_details.append({
            "step": self.steps,
            "tool": tool_name,
            "args": args,
            "duration_ms": duration_ms,
            "success": success,
            "result_preview": result_preview[:150] if result_preview else "",
            })
    
    def add_error(self, error_type: str, detail: str):
        self.errors.append({
            "step": self.steps,
            "error_type": error_type,
            "detail": detail,
        })
    
    def print_summary(self):
        print("\n" + "═" * 70)
        print("运行报告")
        print("═" * 70)
        print(f"问题:     {self.question}")
        print(f"状态:     {self.status}")
        print(f"耗时:     {self.duration_seconds:.1f}s")
        print(f"步数:     {self.steps}")
        print(f"工具调用:  {self.tool_calls} 次")
        print(f"上下文压缩: {self.compressions} 次")
        print(f"HITL 触发: {self.hitl_triggers} 次")
        print(f"Token:    input={self.total_input_tokens}, output={self.total_output_tokens}, 总计={self.total_tokens}")
        print(f"成本:     ${self.estimated_cost_usd:.4f}")
        print(f"最终答案：    {self.final_answer}")

        if self.errors:
            print(f"\n遇到 {len(self.errors)} 个错误:")
            for err in self.errors[:3]:
                print(f"  - [step {err['step']}] {err['type']}: {err['detail'][:80]}")
        
        if self.tool_call_details:
            print(f"\n 工具调用明细:")
            for tc in self.tool_call_details:
                status_icon = "✅" if tc["success"] else "❌"
                print(f"  {status_icon} step {tc['step']}: {tc['tool']}({tc['args']}) "
                      f"[{tc['duration_ms']:.0f}ms]")
        
        print("═" * 70)

    def to_dict(self) -> dict:
        """导出为字典，便于持久化或 JSON 输出"""
        return {
            "question": self.question,
            "status": self.status,
            "duration_seconds": self.duration_seconds,
            "steps": self.steps,
            "tool_calls": self.tool_calls,
            "compressions": self.compressions,
            "hitl_triggers": self.hitl_triggers,
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "final_answer": self.final_answer,
            "errors": self.errors,
            "tool_call_details": self.tool_call_details,
        }


