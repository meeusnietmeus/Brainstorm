import uuid
from datetime import UTC, datetime


def new_id() -> str:
    return str(uuid.uuid4())


def utc_now() -> str:
    """ISO-8601 UTC timestamp with millisecond precision (sorts lexicographically)."""
    return datetime.now(UTC).isoformat(timespec="milliseconds")
