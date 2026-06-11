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
def safe_execute(
    metadata: ToolMetadata,
    tool_args: dict,
    approver: CLIApprover = default_approver,
    agent_reasoning: str = "",
) -> Any:
    """
    根据工具危险等级，自动应用相应的安全策略
    """
    level = metadata.danger_level
    
    # BLACK: 永久禁止
    if level == DangerLevel.BLACK:
        raise ToolHumanRejected(
            f"工具 {metadata.name} 被列入黑名单，永久禁止执行"
        )
    
    # RED: 必须人工确认
    if level == DangerLevel.RED:
        approved = approver.request_approval(
            tool_name=metadata.name,
            tool_args=tool_args,
            reasoning=agent_reasoning,
        )
        if not approved:
            raise ToolHumanRejected(
                f"用户拒绝执行 {metadata.name}({tool_args})"
            )
        print(f"✅ 用户已批准 {metadata.name}")
    
    # YELLOW: 执行前打审计日志（不阻塞）
    if level == DangerLevel.YELLOW:
        print(f"📝 [审计] 即将执行 {metadata.name}({tool_args})")
    
    # GREEN / YELLOW / RED(已批准): 实际执行
    return metadata.func(**tool_args)