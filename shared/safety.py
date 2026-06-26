"""
工具危险等级 + HITL 机制
"""
from enum import Enum
from dataclasses import dataclass
from typing import Callable, Any
import json
from shared.agent_errors import ToolHumanRejected


class DangerLevel(str, Enum):
    GREEN = "green"      # 自主执行
    YELLOW = "yellow"    # 执行前打日志
    RED = "red"          # 必须人工确认
    BLACK = "black"      # 永久禁止


@dataclass
class ToolMetadata:
    """工具元数据：名字 + 危险等级 + 描述"""
    name: str
    func: Callable
    danger_level: DangerLevel
    description: str = ""


# ===== HITL 确认器（命令行版）=====
class CLIApprover:
    """命令行人工确认。生产环境会换成 Web 审批"""
    
    def request_approval(
        self,
        tool_name: str,
        tool_args: dict,
        reasoning: str = "",
    ) -> bool:
        print("\n" + "🚨" * 30)
        print(f"⚠️  [HITL] Agent 请求执行高危操作")
        print(f"工具: {tool_name}")
        print(f"参数: {json.dumps(tool_args, ensure_ascii=False, indent=2)}")
        if reasoning:
            print(f"Agent 的理由: {reasoning}")
        print("🚨" * 30)
        
        while True:
            choice = input("是否批准？(y=批准 / n=拒绝 / d=查看详情): ").strip().lower()
            if choice == "y":
                return True
            elif choice == "n":
                return False
            elif choice == "d":
                print(f"完整参数: {tool_args}")
                continue
            else:
                print("请输入 y / n / d")


# 全局 approver（生产环境会注入不同实现）
default_approver = CLIApprover()


# ===== 安全执行器 =====
# 在 shared/safety.py 里改 safe_execute
def safe_execute(metadata, tool_args, approver=default_approver, agent_reasoning=""):
    from shared.rate_limiter import tracker
    from shared.agent_errors import ToolRateLimit
    from shared.audit_log import audit
    import time
    
    start = time.time()
    approved = None
    error_msg = ""
    result = ""

    # ★ 新增：在执行前做限流检查
    if not tracker.record(metadata.name):
        raise ToolRateLimit(
            f"Tool {metadata.name} rate limit exceeded",
            retry_after=60.0,
        )
    
    try:
        if metadata.danger_level == DangerLevel.BLACK:
            error_msg = "工具被黑名单拦截"
            raise ToolHumanRejected(error_msg)
        
        if metadata.danger_level == DangerLevel.RED:
            approved = approver.request_approval(
                tool_name=metadata.name,
                tool_args=tool_args,
                reasoning=agent_reasoning,
            )
            if not approved:
                error_msg = "用户拒绝执行"
                raise ToolHumanRejected(error_msg)
        
        result = metadata.func(**tool_args)
        return result
    
    except Exception as e:
        if not error_msg:
            error_msg = str(e)
        raise
    finally:
        audit.log(
            event_type="tool_call",
            tool_name=metadata.name,
            tool_args=tool_args,
            danger_level=metadata.danger_level.value,
            approved=approved,
            result=str(result),
            error=error_msg,
            duration_ms=(time.time() - start) * 1000,
        )