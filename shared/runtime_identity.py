import os
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

@dataclass(frozen=True)
class RuntimeIdentity:
    instance_id: str
    hostname: str
    process_id: int
    started_at: datetime

def create_runtime_identity() -> RuntimeIdentity:
    hostname = socket.gethostname()
    process_id = os.getpid()
    random_suffix = uuid4().hex[:8]

    return RuntimeIdentity(
        instance_id=(
            f"{hostname}-{process_id}-{random_suffix}"
        ),
        hostname=hostname,
        process_id=process_id,
        started_at=datetime.now(timezone.utc),
    )

runtime_identity = create_runtime_identity()