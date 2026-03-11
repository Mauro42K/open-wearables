"""MCP tools for querying selected time series metrics."""

import logging
from collections import Counter

from fastmcp import FastMCP

from app.services.api_client import client
from app.utils import normalize_datetime

logger = logging.getLogger(__name__)

ALLOWED_TYPES = {"heart_rate", "steps", "resting_heart_rate"}
ALLOWED_RESOLUTIONS = {"raw", "1min", "5min", "15min", "1hour"}

# Create router for timeseries-related tools
timeseries_router = FastMCP(name="Timeseries Tools")


@timeseries_router.tool
async def get_timeseries(
    user_id: str,
    start_time: str,
    end_time: str,
    types: list[str],
    resolution: str = "raw",
    limit: int = 100,
    cursor: str | None = None,
) -> dict:
    """
    Get selected time series samples for a user within a time range.

    This initial MCP tool is intentionally limited to a small exploration-oriented subset:
    - heart_rate
    - steps
    - resting_heart_rate

    Args:
        user_id: UUID of the user. Use get_users to discover available users.
        start_time: Start datetime in ISO 8601 or YYYY-MM-DD format.
        end_time: End datetime in ISO 8601 or YYYY-MM-DD format.
        types: One or more allowed series types.
        resolution: Sampling resolution. One of raw, 1min, 5min, 15min, 1hour.
        limit: Maximum number of samples to return.
        cursor: Pagination cursor returned by a previous call.

    Returns:
        A dictionary containing:
        - user: Information about the user (id, first_name, last_name)
        - period: The time range queried (start, end)
        - requested_types: The series types requested
        - records: List of timeseries samples
        - summary: Aggregate counts by type
        - pagination: Cursor pagination details
        - metadata: Backend metadata about the query

    Notes for LLMs:
        - Call get_users first to get the user_id.
        - This tool is intentionally limited to a small subset of series types for now.
        - Timeseries data can be high-volume; use limit and cursor to page through results.
        - For daily rollups, prefer the summary tools over raw timeseries.
    """
    try:
        try:
            user_data = await client.get_user(user_id)
            user = {
                "id": str(user_data.get("id")),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
            }
        except ValueError as e:
            return {"error": f"User not found: {user_id}", "details": str(e)}

        requested_types = list(dict.fromkeys(types))
        invalid_types = [series_type for series_type in requested_types if series_type not in ALLOWED_TYPES]
        if invalid_types:
            return {
                "error": "Unsupported timeseries type requested.",
                "requested_types": requested_types,
                "unsupported_types": invalid_types,
                "allowed_types": sorted(ALLOWED_TYPES),
            }

        if resolution not in ALLOWED_RESOLUTIONS:
            return {
                "error": "Unsupported resolution requested.",
                "requested_resolution": resolution,
                "allowed_resolutions": sorted(ALLOWED_RESOLUTIONS),
            }

        timeseries_response = await client.get_timeseries(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            types=requested_types,
            resolution=resolution,
            limit=limit,
            cursor=cursor,
        )

        records_data = timeseries_response.get("data", [])
        type_counts: Counter[str] = Counter()
        records = []

        for record in records_data:
            series_type = record.get("type")
            if series_type:
                type_counts[series_type] += 1

            source = record.get("source", {})
            records.append(
                {
                    "timestamp": normalize_datetime(record.get("timestamp")),
                    "type": series_type,
                    "value": record.get("value"),
                    "unit": record.get("unit"),
                    "source": source.get("provider") if isinstance(source, dict) else source,
                    "device": source.get("device") if isinstance(source, dict) else None,
                }
            )

        pagination = timeseries_response.get("pagination", {})
        metadata = timeseries_response.get("metadata", {})

        return {
            "user": user,
            "period": {"start": start_time, "end": end_time},
            "requested_types": requested_types,
            "records": records,
            "summary": {
                "sample_count": len(records),
                "counts_by_type": dict(type_counts),
            },
            "pagination": {
                "next_cursor": pagination.get("next_cursor"),
                "previous_cursor": pagination.get("previous_cursor"),
                "has_more": pagination.get("has_more"),
                "total_count": pagination.get("total_count"),
            },
            "metadata": {
                "resolution": metadata.get("resolution"),
                "sample_count": metadata.get("sample_count"),
                "start_time": metadata.get("start_time"),
                "end_time": metadata.get("end_time"),
            },
        }

    except ValueError as e:
        logger.error(f"API error in get_timeseries: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in get_timeseries: {e}")
        return {"error": f"Failed to fetch timeseries: {e}"}
