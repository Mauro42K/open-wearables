"""Remote MCP tool for workout events."""

from fastmcp import FastMCP

from app.services.backend_client import ResourceNotFoundError
from app.services.tool_execution_guard import ToolExecutionContext, execute_guarded_tool
from app.utils import normalize_datetime

workouts_router = FastMCP(name="Workout Tools")


@workouts_router.tool
async def get_workout_events(
    user_id: str,
    start_date: str,
    end_date: str,
    workout_type: str | None = None,
) -> dict:
    """Get workout events for a user within a date range."""

    async def operation(context: ToolExecutionContext) -> dict:
        try:
            user_data = await context.api_client.get_user(user_id)
        except ResourceNotFoundError:
            return {"error": "unexpected_error", "message": "User not found."}

        workouts_response = await context.api_client.get_workouts(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
            record_type=workout_type,
        )
        records_data = workouts_response.get("data", [])

        records = []
        durations = []
        distances = []
        calories = []
        workout_types: dict[str, int] = {}

        for record in records_data:
            duration = record.get("duration_seconds")
            distance = record.get("distance_meters")
            calories_kcal = record.get("calories_kcal")
            record_type = record.get("type", "unknown")

            if duration is not None:
                durations.append(duration)
            if distance is not None:
                distances.append(distance)
            if calories_kcal is not None:
                calories.append(calories_kcal)
            workout_types[record_type] = workout_types.get(record_type, 0) + 1

            source = record.get("source", {})
            records.append(
                {
                    "id": str(record.get("id")),
                    "type": record_type,
                    "start_datetime": normalize_datetime(record.get("start_time")),
                    "end_datetime": normalize_datetime(record.get("end_time")),
                    "duration_seconds": duration,
                    "distance_meters": distance,
                    "calories_kcal": calories_kcal,
                    "avg_heart_rate_bpm": record.get("avg_heart_rate_bpm"),
                    "max_heart_rate_bpm": record.get("max_heart_rate_bpm"),
                    "avg_pace_sec_per_km": record.get("avg_pace_sec_per_km"),
                    "elevation_gain_meters": record.get("elevation_gain_meters"),
                    "source": source.get("provider") if isinstance(source, dict) else source,
                }
            )

        total_duration = sum(durations)
        total_distance = sum(distances)
        total_calories = sum(calories)

        return {
            "user": {
                "id": str(user_data.get("id")),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
            },
            "period": {"start": start_date, "end": end_date},
            "records": records,
            "summary": {
                "total_workouts": len(records),
                "workouts_with_distance": len(distances),
                "total_duration_seconds": total_duration,
                "total_distance_meters": total_distance if distances else None,
                "total_calories_kcal": round(total_calories, 1) if calories else None,
                "avg_duration_seconds": round(total_duration / len(durations)) if durations else None,
                "workout_types": workout_types if workout_types else None,
            },
        }

    return await execute_guarded_tool(operation)
