"""
跑几个任务后，查询审计日志
"""
# import sys, os
# sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# from shared.audit_log import audit

# # 跑完之前的 02_hitl_agent.py 后，查询审计日志

# print("=== 所有红色工具调用 ===")
# red_calls = audit.query(danger_level="red")
# for call in red_calls:
#     print(f"  {call['ts']}: {call['tool_name']}({call['tool_args']}) "
#           f"批准={call['approved']}")

# print("\n=== 所有失败的调用 ===")
# all_calls = audit.query(event_type="tool_call")
# failed = [c for c in all_calls if c["error"]]
# for call in failed:
#     print(f"  {call['ts']}: {call['tool_name']} - {call['error'][:80]}")

# print(f"\n=== 总统计 ===")
# print(f"  总调用次数: {len(all_calls)}")
# print(f"  失败次数: {len(failed)}")
# print(f"  红色工具调用: {len(red_calls)}")

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from datetime import datetime, timedelta
from shared.audit_log import audit

# 测试 1：只用时间范围
now = datetime.now()
recent = audit.query(time_range=(
    (now - timedelta(hours=1)).isoformat(),
    now.isoformat()
))
print(f"过去 1 小时的日志: {len(recent)} 条")

# 测试 2：时间范围 + 字段匹配（组合）
red_calls_today = audit.query(
    danger_level="red",
    time_range=(
        now.replace(hour=0, minute=0, second=0).isoformat(),
        now.isoformat()
    )
)
print(f"今天的红色工具调用: {len(red_calls_today)} 条")

# 测试 3：只用字段（不传 time_range）
all_red = audit.query(danger_level="red")
print(f"所有红色工具调用: {len(all_red)} 条")