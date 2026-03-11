"""Small utility helpers for ow-mcp."""

from datetime import datetime


def normalize_datetime(value: str | None) -> str | None:
    """Normalize ISO datetimes into a consistent representation."""
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value
