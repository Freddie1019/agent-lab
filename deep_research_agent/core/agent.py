"""
ResearchAgent：深度研究 Agent 主类
整合前 6 天所有能力：
- ReAct 循环（Day 3）
- 上下文管理（Day 4）
- 真实工具（Day 5）
- 错误处理 + HITL + 审计（Day 6）
"""


from itertools import accumulate
from nt import error
import os, sys

from openai import max_retries
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import json
import time

import asyncio
import json
from typing import AsyncIterator, Optional
from deep_research_agent.core.events import AgentEvent, agent_error_to_event, make_error_event

from shared.llm_client import client, DEFAULT_MODEL
from shared.context_manager import ContextManager
from shared.token_counter import count_messages_tokens
from shared.safety import safe_execute, CLIApprover
from shared.agent_errors import AgentError, classify_exception, ToolTimeout, ToolUnavailable
from shared.audit_log import audit

from deep_research_agent.core.prompts import RESEARCH_SYSTEM_PROMPT
from deep_research_agent.core.tools import (
    RESEARCH_TOOLS, RESEARCH_TOOLS_SCHEMA, get_tool_by_name,
)
from deep_research_agent.core.report import RunReport

class ResearchAgent:
    """
    深度研究 Agent
    
    用法：
        agent = ResearchAgent()
        report = agent.run("2025 年最火的开源 Agent 框架是哪些？")
        print(report.final_answer)
    """
    
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_steps: int = 10,
        max_tokens_budget: int = 5000,
        max_context_tokens: int = 8000,
        context_strategy: str = "sliding_window",
        verbose: bool = True,
        auto_retry_recoverable: bool = True
    ):
        self.model = model
        self.max_steps = max_steps
        self.max_tokens_budget = max_tokens_budget
        self.verbose = verbose

        self.context_manage = ContextManager(
            strategy=context_strategy,
            max_tokens=max_context_tokens,
            keep_recent_messages=9,
        )

        self.approver= CLIApprover()
        self.auto_retry_recoverable = auto_retry_recoverable
    
    def _log(self, msg: str):
        if self.verbose:
            print(msg)
    
    async def _execute_tool_with_retry(
        self,
        metadata,
        tool_args: dict,
        step: int,
        max_retries: int = 1,
    ):
        """ 带自动重试的工具执行 """
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                result = safe_execute(
                    metadata=metadata,
                    tool_args=tool_args,
                    approver=self.approver,
                )
                return ("success", result, None)
            except (ToolTimeout, ToolUnavailable) as e:
                last_error = e
                if attempt < max_retries:
                    # 可恢复错误，等一下再试
                    await asyncio.sleep(2 ** attempt)  # 指数退避
                    continue
                return ("error_retried_fail", None, e)
            except AgentError as e:
                # 不可恢复错误，直接失败
                return ("error_no_retry", None, e)
            except Exception as e:
                err = classify_exception(e)
                return ("error_no_retry", None, err)
        
        return ("error_retried_fail", None, last_error)
    
    def run(self, question: str) -> RunReport:
        "执行一次研究任务，返回完整报告"
        report = RunReport(question=question)

        self._log(f"\n{'═' * 70}")
        self._log(f"研究问题: {question}")
        self._log(f"{'═' * 70}\n")

        messages = [
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": question}
        ]

        for step in range(1, self.max_steps + 1):
            report.steps = step
            self._log(f"━━━ 第 {step} 步 ━━━")

            # 1. token 预算检查
            if report.total_tokens >= self.max_tokens_budget:
                self._log(f"Token 预算耗尽 ({report.total_tokens}/{self.max_tokens_budget})")
                report.status = "token_limit"
                report.add_error("token_budget", "Token 预算耗尽")
                break
            
            # 2. 上下文压缩
            if self.context_manage.needs_compression(messages):
                before = count_messages_tokens(messages)
                messages = self.context_manage.compress(messages)
                after = count_messages_tokens(messages)
                report.compressions += 1
                self._log(f"  [压缩] {before} → {after} tokens")
            
            # 3. 调用 LLM
            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=RESEARCH_TOOLS_SCHEMA,
                    temperature=0,
                )
            except Exception as e:
                err = classify_exception(e)
                self._log(f"LLM 调用失败: {err.to_llm_message()}")
                report.status = "error"
                report.add_error("llm_failure", str(e))
                break
            
            # 4. 统计 token
            report.total_input_tokens = response.usage.prompt_tokens
            report.total_output_tokens = response.usage.completion_tokens

            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            messages.append(msg)
            
            # 5. 判断状态
            if finish_reason == "stop":
                self._log(f"\n 任务完成")
                report.status = "success"
                report.final_answer = msg.content
                break

            if finish_reason == "tool_calls":
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)
                
                    metadata = get_tool_by_name(tool_name)
                    if metadata is None:
                        result = f"未知工具: {tool_name}"
                        success = False
                    else:
                        self._log(f"[{metadata.danger_level.value.upper()}] "
                                 f"{tool_name}({tool_args})")
                        
                        tool_start = time.time()
                        try:
                            result = safe_execute(
                                metadata=metadata,
                                tool_args=tool_args,
                                approver=self.approver,
                                agent_reasoning=msg.content or "",
                            )
                            success = True
                            if metadata.danger_level.value == "red":
                                report.hitl_triggers += 1
                        except AgentError as e:
                            result = e.to_llm_message()
                            success = False
                            report.add_error("tool_failure", str(e))
                        except Exception as e:
                            err = classify_exception(e)
                            result = err.to_llm_message()
                            success = False
                            report.add_error("tool_failure", str(e))
                        
                        elapsed_ms = (time.time() - tool_start) * 1000
                        report.add_to_call(
                            tool_name=tool_name,
                            args=tool_args,
                            duration_ms=elapsed_ms,
                            success=success,
                            result_preview=str(result),
                        )
                    result_str = str(result)
                    # self._log(f"📋 {result_str[:2000]}")
                    self._log(f"📋 {result_str}")

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                    })
                continue

            # 6. 其他异常 finish_reason
            self._log(f"⚠️ 异常 finish_reason: {finish_reason}")
            report.status = "error"
            report.add_error("abnormal_finish", finish_reason)
            break
        else:
            # 没有 break，说明走到 max_steps
            self._log(f"⛔ 达到最大步数 {self.max_steps}")
            report.status = "max_steps"
        
        report.end_time = time.time()
        
        # 审计日志
        audit.log(
            event_type="agent_run",
            user_id="cli_user",
            result=report.final_answer or "",
            duration_ms=report.duration_seconds * 1000,
        )
        
        return report    

    async def stream_with_history(
            self, 
            messages: list[dict]
        ) -> AsyncIterator[AgentEvent]:
        """
        流式 Agent v2: 增强错误处理
        """

        # ===== 开始事件 =====
        yield AgentEvent(
            type="agent_start",
            data={"messages_count": len(messages)},
        )
        
        accumulated_answer= "" # 累计已生成的内容，错误时返回给客户端

        for step in range(1, self.max_steps + 1):
            yield AgentEvent(type="step_start", step=step, data={"step": step})

            try:
                response = client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=RESEARCH_TOOLS_SCHEMA,
                    temperature=0,
                )
            except Exception as e:
                err = classify_exception(e)
                yield agent_error_to_event(
                    err,
                    step=step,
                    accumulated_content=accumulated_answer or None,
                )
                return  # 流终止
            
            msg = response.choices[0].message
            finish_reason = response.choices[0].finish_reason
            messages.append(msg)

            # 思考事件
            if msg.content:
                accumulated_answer = msg.content
                yield AgentEvent(
                    type="thought",
                    step=step,
                    data={"content": msg.content},
                )
            
            # 完成
            if finish_reason == "stop":
                yield AgentEvent(
                    type="answer_complete",
                    step=step,
                    data={"answer": msg.content or ""},
                )
                yield AgentEvent(
                    type="agent_complete",
                    step=step,
                    data={"status": "success", "total_steps": step},
                )
                return
            
            # 工具调用
            if finish_reason == "tool_calls":
                for tc in msg.tool_calls:
                    tool_name = tc.function.name
                    tool_args = json.loads(tc.function.arguments)
                    
                    # 事件 1：通知客户端我要调工具了
                    yield AgentEvent(
                        type="tool_call",
                        step=step,
                        data={"tool_name": tool_name, "tool_args": tool_args},
                    )
                    
                    # 实际调用
                    metadata = get_tool_by_name(tool_name)

                    # if self.auto_retry_recoverable:
                    #     status, result, error = await self._execute_tool_with_retry(
                    #         metadata, tool_args, step, max_retries=1,
                    #     )
                    # else:
                    if metadata is None:
                        result = f"未知工具: {tool_name}"
                        success = False
                    else:
                        try:
                            result = safe_execute(
                                metadata=metadata,
                                tool_args=tool_args,
                                approver=self.approver,
                            )
                            success = True
                        except AgentError as e:
                            # ★ 双向通知：客户端 + LLM
                            # 1. 推送错误事件给客户端
                            yield agent_error_to_event(
                                e, step=step,
                                tool_name=tool_name,
                                accumulated_content=accumulated_answer or None
                            )
                            # 2. 把错误也传给 LLM （让它决定要不要换策略）
                            result = e.to_llm_message()
                            success = False
                        except Exception as e:
                            err = classify_exception(e)
                            yield agent_error_to_event(
                                e, step=step,
                                tool_name=tool_name,
                                accumulated_content=accumulated_answer or None
                            )
                            result = err.to_llm_message()
                            success = False
                    
                    # 事件 2：返回工具结果
                    yield AgentEvent(
                        type="tool_result",
                        step=step,
                        data={
                            "tool_name": tool_name,
                            "success": success,
                            "result_preview": str(result)[:300],
                        },
                    )
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": str(result),
                    })
                continue

            # ===== 异常 finish_reason =====
            yield make_error_event(
                type="abnormal_finish",
                title="Abnormal Finish Reason",
                detail=f"finish_reason={finish_reason}",
                user_message=f"LLM 返回了非预期的状态: {finish_reason}",
                step=step,
                recoverable=False,
                accumulated_content=accumulated_answer or None,
            )
            return
        
        # ===== max_steps 用完 =====
        yield make_error_event(
            type="max_steps_exceeded",
            title="Max Steps Exceeded",
            detail=f"Agent 达到最大步数 {self.max_steps}",
            user_message="研究步骤太多，已自动停止。请尝试更具体的问题。",
            step=self.max_steps,
            severity="warning",
            recoverable=False,
            accumulated_content=accumulated_answer or None,
        )
