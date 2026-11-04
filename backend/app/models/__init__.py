import uuid
from datetime import datetime, timezone

from sqlalchemy import event
from sqlalchemy.engine import Engine


def new_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _record):
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


from app.models.profile import PROFILE_STATUSES, BusinessProfile  # noqa: E402
from app.models.run import RUN_STATUSES, PipelineRun  # noqa: E402
from app.models.query import DiscoveredQuery  # noqa: E402
from app.models.recommendation import (  # noqa: E402
    CONTENT_TYPES,
    PRIORITIES,
    ContentRecommendation,
)

__all__ = [
    "BusinessProfile",
    "PipelineRun",
    "DiscoveredQuery",
    "ContentRecommendation",
    "PROFILE_STATUSES",
    "RUN_STATUSES",
    "CONTENT_TYPES",
    "PRIORITIES",
]
