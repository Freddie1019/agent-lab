import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from deep_research_agent.core.db.repositories import run_repo
from deep_research_agent.core.db.session import AsyncSessionLocal
from deep_research_agent.core.run import (
    AgentRun,
    AgentRunStatus,
)
from deep_research_agent.core.run_health import (
    ReconciliationItem,
    ReconciliationReport,
    RunHealthResponse,
    RunHealthState,
)
from deep_research_agent.core.settings import get_settings
from shared.runtime_identity import runtime_identity

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {
    AgentRunStatus.COMPLETED,
    AgentRunStatus.FAILED,
    AgentRunStatus.INTERRUPTED,
    AgentRunStatus.CANCELLED,
}

@dataclass
class RunHeartbeatHandle:
    run_id: str
    runtime_id: str
    stop_event: asyncio.Event
    task: asyncio.Task

    async def stop(self) -> None:
        self.stop_event.set()
        self.task.cancel()

        with suppress(asyncio.CancelledError):
            await self.task


@dataclass
class RunReconcilerHandle:
    stop_event: asyncio.Event
    task: asyncio.Task

    async def stop(self) -> None:
        self.stop_event.set()
        self.task.cancel()

        with suppress(asyncio.CancelledError):
            await self.task


class RunHealthService:
    def start_reconciler(self) -> RunReconcilerHandle:
        """Start the periodic stale-Run reconciliation worker."""
        stop_event = asyncio.Event()
        task = asyncio.create_task(
            self._reconciliation_loop(stop_event=stop_event),
            name="run-stale-reconciler",
        )
        return RunReconcilerHandle(
            stop_event=stop_event,
            task=task,
        )

    async def _reconciliation_loop(
        self,
        *,
        stop_event: asyncio.Event,
    ) -> None:
        interval = get_settings().RUN_RECONCILE_INTERVAL_SECONDS

        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval,
                )
                break
            except asyncio.TimeoutError:
                pass

            try:
                report = await self.reconcile_stale_runs()
                if report.repaired_count:
                    logger.warning(
                        "Periodic stale Run reconciliation repaired=%s",
                        report.repaired_count,
                    )
            except Exception:
                logger.exception(
                    "Periodic stale Run reconciliation failed"
                )

    async def start_monitor(
        self,
        *,
        run_id: str,
        user_id: str,
    ) -> RunHeartbeatHandle:
        """
        绑定当前 Runtime， 并启动 Heartbeat 后台任务
        """
        runtime_id = runtime_identity.instance_id

        async with AsyncSessionLocal() as db:
            await run_repo.claim_runtime(
                db=db,
                run_id=run_id,
                user_id=user_id,
                runtime_id=runtime_id,
            )

        stop_event = asyncio.Event()

        task = asyncio.create_task(
            self._heartbeat_loop(
                run_id=run_id,
                runtime_id=runtime_id,
                stop_event=stop_event,
            ),
            name=f"heartbeat:{run_id}",
        )

        return RunHeartbeatHandle(
            run_id=run_id,
            runtime_id=runtime_id,
            stop_event=stop_event,
            task=task,
        )

    async def _heartbeat_loop(
        self,
        *,
        run_id: str,
        runtime_id: str,
        stop_event: asyncio.Event,
    ) -> None:
        interval = (
            get_settings().RUN_HEARTBEAT_INTERVAL_SECONDS
        )

        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=interval,
                )
                break
            except asyncio.TimeoutError:
                pass

            try:
                async with AsyncSessionLocal() as db:
                    updated = await run_repo.touch_heartbeat(
                        db=db,
                        run_id=run_id,
                        runtime_id=runtime_id,
                    )

                if not updated:
                    logger.info(
                        "Heartbeat stopped because Run"
                        "is no longer active: run_id=%s",
                        run_id
                    )
                    return

            except Exception:
                logger.exception(
                    "Heartbeat update failed: run_id=%s",
                    run_id,
                )

    async def reconcile_stale_runs(
        self,
    ) -> ReconciliationReport:
        """
        查找并修复所有 Stale Run
        """
        checked_at = datetime.now(timezone.utc)

        report = ReconciliationReport(
            checked_at=checked_at,
            stale_after_seconds=(
                get_settings().RUN_STALE_AFTER_SECONDS
            ),
        )

        async with AsyncSessionLocal() as db:
            stale_runs = await run_repo.find_stale_runs(
                db=db,
                stale_after_seconds=(
                    get_settings().RUN_STALE_AFTER_SECONDS
                ),
            )

            for run in stale_runs:
                previous_status = run.status.value

                try:
                    repaired = (
                        await run_repo.mark_stale_interrupted(
                            db=db,
                            run=run,
                        )
                    )
                except Exception:
                    logger.exception(
                        "Stale Run reconciliation failed: %s",
                        run.id
                    )
                    continue

                # A heartbeat renewed the lease after the stale scan.
                if repaired is None:
                    continue

                requires_manual_review = (
                    previous_status
                    == AgentRunStatus.WAITING_TOOL.value
                )

                report.items.append(
                    ReconciliationItem(
                        run_id=repaired.id,
                        previous_status=previous_status,
                        new_status=repaired.status.value,
                        runtime_id=repaired.runtime_id,
                        error_type=(
                            repaired.error_type
                            or "stale_run_detected"
                        ),
                        requires_manual_review=(
                            requires_manual_review
                        ),
                    )
                )
            report.repaired_count = len(report.items)

        return report

    def build_health_response(
        self,
        run: AgentRun,
    ) -> RunHealthResponse:
        now = datetime.now(timezone.utc)

        if run.status in TERMINAL_STATUSES:
            return RunHealthResponse(
                run_id=run.id,
                run_status=run.status.value,
                health_state=RunHealthState.TERMINAL,
                runtime_id=run.runtime_id,
                last_heartbeat_at=run.last_heartbeat_at,
                stale_after_seconds=(
                    get_settings().RUN_STALE_AFTER_SECONDS
                ),
                detail="Run 已经进入终态"
            )
        if run.last_heartbeat_at is None:
            orphaned = (
                run.status
                in {
                    AgentRunStatus.RUNNING,
                    AgentRunStatus.WAITING_TOOL,
                }
                and run.runtime_id is None
            )
            return RunHealthResponse(
                run_id=run.id,
                run_status=run.status.value,
                health_state=(
                    RunHealthState.STALE
                    if orphaned
                    else RunHealthState.UNKNOWN
                ),
                runtime_id=run.runtime_id,
                last_heartbeat_at=None,
                heartbeat_age_seconds=None,
                stale_after_seconds=(
                    get_settings().RUN_STALE_AFTER_SECONDS
                ),
                detail=(
                    "Run 没有执行实例或 Heartbeat"
                    if orphaned
                    else "Run 尚未写入 Heartbeat"
                ),
            )

        heartbeat_at = run.last_heartbeat_at

        if heartbeat_at.tzinfo is None:
            heartbeat_at = heartbeat_at.replace(
                tzinfo=timezone.utc
            )

        heartbeat_age = (
            now - heartbeat_at
        ).total_seconds()

        stale = (
            heartbeat_age > get_settings().RUN_STALE_AFTER_SECONDS
        )

        return RunHealthResponse(
            run_id=run.id,
            run_status=run.status.value,
            health_state=(
                RunHealthState.STALE
                if stale
                else RunHealthState.HEALTHY
            ),
            runtime_id=run.runtime_id,
            last_heartbeat_at=run.last_heartbeat_at,
            heartbeat_age_seconds=heartbeat_age,
            stale_after_seconds=(
                get_settings().RUN_STALE_AFTER_SECONDS
            ),
            detail=(
                "Heartbeat 已经过期"
                if stale
                else "Run Heartbeat 正常"
            )
        )

run_health_service = RunHealthService()
        

        
    
