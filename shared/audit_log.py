"""
审计日志：所有工具调用、HITL 决策都留痕
生产环境会写数据库，这里先用 JSON Lines 文件
"""
import json
import time
import pathlib
from typing import Optional
from datetime import datetime

AUDIT_LOG_PATH = pathlib.Path("./audit.log")

class AuditLogger:
    def __init__(self, log_path: pathlib.Path = AUDIT_LOG_PATH):
        self.log_path = log_path
    
    def log(
        self,
        event_type: str,
        tool_name: str = "",
        tool_args: dict = None,
        result: str = "",
        danger_level: str = "",
        approved: Optional[bool] = None,
        error: str = "",
        duration_ms: float = 0,
        user_id: str = "anonymous",
    ):
        entry = {
            "ts": datetime.now().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "tool_name": tool_name,
            "tool_args": tool_args or {},
            "danger_level": danger_level,
            "approved": approved,
            "result_preview": result[:200] if result else "",
            "error": error,
            "duration_ms": duration_ms,
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
    def query(self, **filters) -> list:
        """
        查询审计日志
        支持：
        - 字段精确匹配：query(tool_name="delete_file", approved=False)
        - 时间范围查询：query(time_range=("2026-06-13T00:00", "2026-06-13T23:59"))
        - 两者可组合
        """
        results = []
        if not self.log_path.exists():
            return results
    
        # ★ 提取并预解析时间范围（循环不变量）
        time_range = filters.pop("time_range", None)
        start_time = None
        end_time = None
        if time_range:
            start_str, end_str = time_range
            start_time = datetime.fromisoformat(start_str)
            end_time = datetime.fromisoformat(end_str)
        
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue  # 损坏的日志行跳过
                
                # 字段精确匹配
                if not all(entry.get(k) == v for k, v in filters.items()):
                    continue
                
                # 时间范围校验
                if start_time:
                    entry_time_str = entry.get("ts")
                    if entry_time_str:
                        try:
                            entry_time = datetime.fromisoformat(entry_time_str)
                            if not (start_time <= entry_time <= end_time):
                                continue
                        except ValueError:
                            continue  # ts 格式错误，跳过
                    else:
                        continue  # 你的选择：缺时间戳跳过
                
                results.append(entry)
        
        return results
audit = AuditLogger()
