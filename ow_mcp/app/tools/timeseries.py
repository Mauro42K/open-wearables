"""Remote MCP tool for selected timeseries metrics."""

from collections import Counter

from fastmcp import FastMCP

from app.services.backend_client import ResourceNotFoundError
from app.services.tool_execution_guard import ToolExecutionContext, execute_guarded_tool
from app.utils import normalize_datetime

ALLOWED_TYPES = {"heart_rate", "steps", "resting_heart_rate"}
ALLOWED_RESOLUTIONS = {"raw", "1min", "5min", "15min", "1hour"}

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
    """Get selected timeseries samples for a user within a time range."""

    async def operation(context: ToolExecutionContext) -> dict:
        try:
            user_data = await context.api_client.get_user(user_id)
        except ResourceNotFoundError:
            return {"error": "unexpected_error", "message": "User not found."}

        requested_types = list(dict.fromkeys(types))
        invalid_types = [series_type for series_type in requested_types if series_type not in ALLOWED_TYPES]
        if invalid_types:
            return {
                "error": "unexpected_error",
                "message": (
                    "Unsupported timeseries type requested. "
                    f"Allowed types: {', '.join(sorted(ALLOWED_TYPES))}."
                ),
            }

        if resolution not in ALLOWED_RESOLUTIONS:
            return {
                "error": "unexpected_error",
                "message": (
                    "Unsupported resolution requested. "
                    f"Allowed resolutions: {', '.join(sorted(ALLOWED_RESOLUTIONS))}."
                ),
            }

        timeseries_response = await context.api_client.get_timeseries(
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
            "user": {
                "id": str(user_data.get("id")),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
            },
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

    return await execute_guarded_tool(operation)
