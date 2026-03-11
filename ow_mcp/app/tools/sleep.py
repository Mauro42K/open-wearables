"""Remote MCP tool for sleep summaries."""

from fastmcp import FastMCP

from app.services.backend_client import ResourceNotFoundError
from app.services.tool_execution_guard import ToolExecutionContext, execute_guarded_tool
from app.utils import normalize_datetime

sleep_router = FastMCP(name="Sleep Tools")


@sleep_router.tool
async def get_sleep_summary(
    user_id: str,
    start_date: str,
    end_date: str,
) -> dict:
    """Get daily sleep summaries for a user within a date range."""

    async def operation(context: ToolExecutionContext) -> dict:
        try:
            user_data = await context.api_client.get_user(user_id)
        except ResourceNotFoundError:
            return {"error": "unexpected_error", "message": "User not found."}

        sleep_response = await context.api_client.get_sleep_summaries(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        records_data = sleep_response.get("data", [])

        records = []
        durations = []

        for record in records_data:
            duration = record.get("duration_minutes")
            if duration is not None:
                durations.append(duration)

            source = record.get("source", {})
            records.append(
                {
                    "date": str(record.get("date")),
                    "start_datetime": normalize_datetime(record.get("start_time")),
                    "end_datetime": normalize_datetime(record.get("end_time")),
                    "duration_minutes": duration,
                    "source": source.get("provider") if isinstance(source, dict) else source,
                }
            )

        summary = {
            "total_nights": len(records),
            "nights_with_data": len(durations),
            "avg_duration_minutes": None,
            "min_duration_minutes": None,
            "max_duration_minutes": None,
        }
        if durations:
            average_duration = sum(durations) / len(durations)
            summary.update(
                {
                    "avg_duration_minutes": round(average_duration),
                    "min_duration_minutes": min(durations),
                    "max_duration_minutes": max(durations),
                }
            )

        return {
            "user": {
                "id": str(user_data.get("id")),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
            },
            "period": {"start": start_date, "end": end_date},
            "records": records,
            "summary": summary,
        }

    return await execute_guarded_tool(operation)


@sleep_router.tool
async def get_sleep_sessions(
    user_id: str,
    start_date: str,
    end_date: str,
) -> dict:
    """Get individual sleep sessions for a user within a date range."""

    async def operation(context: ToolExecutionContext) -> dict:
        try:
            user_data = await context.api_client.get_user(user_id)
        except ResourceNotFoundError:
            return {"error": "unexpected_error", "message": "User not found."}

        sleep_response = await context.api_client.get_sleep_sessions(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        records_data = sleep_response.get("data", [])

        records = []
        durations = []
        nap_count = 0

        for record in records_data:
            duration = record.get("duration_seconds")
            is_nap = bool(record.get("is_nap"))

            if duration is not None:
                durations.append(duration)
            if is_nap:
                nap_count += 1

            source = record.get("source", {})
            records.append(
                {
                    "id": str(record.get("id")),
                    "start_datetime": normalize_datetime(record.get("start_time")),
                    "end_datetime": normalize_datetime(record.get("end_time")),
                    "duration_seconds": duration,
                    "efficiency_percent": record.get("efficiency_percent"),
                    "stages": record.get("stages"),
                    "is_nap": is_nap,
                    "source": source.get("provider") if isinstance(source, dict) else source,
                    "device": source.get("device") if isinstance(source, dict) else None,
                }
            )

        return {
            "user": {
                "id": str(user_data.get("id")),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
            },
            "period": {"start": start_date, "end": end_date},
            "records": records,
            "summary": {
                "total_sessions": len(records),
                "sessions_with_duration": len(durations),
                "avg_duration_seconds": round(sum(durations) / len(durations)) if durations else None,
                "nap_count": nap_count,
            },
        }

    return await execute_guarded_tool(operation)
