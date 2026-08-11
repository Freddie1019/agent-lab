from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

class RunHealthState(str, Enum):
    HEALTHY = "healthy"
    STALE = "stale"
    TERMINAL = "terminal"
    UNKNOWN = "unknown"

class RunHealthResponse(BaseModel):
    run_id: str
    run_status: str
    health_state: RunHealthState

    runtime_id: Optional[str] = None
    last_heartbeat_at: Optional[datetime] = None
    heartbeat_age_seconds: Optional[float] = None

    stale_after_seconds: int

    detail: str

class ReconciliationItem(BaseModel):
    run_id: str
    previous_status: str

    new_status: str
    runtime_id: Optional[str] = None
    error_type: str

    requires_manual_review: bool = False

class ReconciliationReport(BaseModel):
    checked_at: datetime
    stale_after_seconds: int

    repaired_count: int = 0

    items: list[ReconciliationItem] = Field(default_factory=list)
