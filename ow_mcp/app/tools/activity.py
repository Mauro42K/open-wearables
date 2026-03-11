"""Remote MCP tool for activity summaries."""

from fastmcp import FastMCP

from app.services.backend_client import ResourceNotFoundError
from app.services.tool_execution_guard import ToolExecutionContext, execute_guarded_tool

activity_router = FastMCP(name="Activity Tools")


@activity_router.tool
async def get_activity_summary(
    user_id: str,
    start_date: str,
    end_date: str,
) -> dict:
    """Get daily activity summaries for a user within a date range."""

    async def operation(context: ToolExecutionContext) -> dict:
        try:
            user_data = await context.api_client.get_user(user_id)
        except ResourceNotFoundError:
            return {"error": "unexpected_error", "message": "User not found."}

        activity_response = await context.api_client.get_activity_summaries(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date,
        )
        records_data = activity_response.get("data", [])

        records = []
        steps_list = []
        distances = []
        active_calories = []
        total_calories = []
        active_minutes_list = []
        intensity_light = []
        intensity_moderate = []
        intensity_vigorous = []

        for record in records_data:
            steps = record.get("steps")
            distance = record.get("distance_meters")
            active_cal = record.get("active_calories_kcal")
            total_cal = record.get("total_calories_kcal")
            active_mins = record.get("active_minutes")
            intensity = record.get("intensity_minutes") or {}
            heart_rate = record.get("heart_rate")

            if steps is not None:
                steps_list.append(steps)
            if distance is not None:
                distances.append(distance)
            if active_cal is not None:
                active_calories.append(active_cal)
            if total_cal is not None:
                total_calories.append(total_cal)
            if active_mins is not None:
                active_minutes_list.append(active_mins)
            if intensity.get("light") is not None:
                intensity_light.append(intensity["light"])
            if intensity.get("moderate") is not None:
                intensity_moderate.append(intensity["moderate"])
            if intensity.get("vigorous") is not None:
                intensity_vigorous.append(intensity["vigorous"])

            source = record.get("source", {})
            records.append(
                {
                    "date": str(record.get("date")),
                    "steps": steps,
                    "distance_meters": distance,
                    "active_calories_kcal": active_cal,
                    "total_calories_kcal": total_cal,
                    "active_minutes": active_mins,
                    "sedentary_minutes": record.get("sedentary_minutes"),
                    "heart_rate": heart_rate,
                    "intensity_minutes": intensity if intensity else None,
                    "floors_climbed": record.get("floors_climbed"),
                    "elevation_meters": record.get("elevation_meters"),
                    "source": source.get("provider") if isinstance(source, dict) else source,
                }
            )

        total_steps = sum(steps_list) if steps_list else None
        total_distance = sum(distances) if distances else None

        return {
            "user": {
                "id": str(user_data.get("id")),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
            },
            "period": {"start": start_date, "end": end_date},
            "records": records,
            "summary": {
                "total_days": len(records),
                "days_with_data": len(steps_list),
                "total_steps": total_steps,
                "avg_steps": round(total_steps / len(steps_list)) if steps_list and total_steps is not None else None,
                "total_distance_meters": total_distance,
                "total_active_calories_kcal": round(sum(active_calories), 1) if active_calories else None,
                "total_calories_kcal": round(sum(total_calories), 1) if total_calories else None,
                "avg_active_minutes": (
                    round(sum(active_minutes_list) / len(active_minutes_list)) if active_minutes_list else None
                ),
                "total_intensity_minutes": {
                    "light": sum(intensity_light) if intensity_light else None,
                    "moderate": sum(intensity_moderate) if intensity_moderate else None,
                    "vigorous": sum(intensity_vigorous) if intensity_vigorous else None,
                }
                if (intensity_light or intensity_moderate or intensity_vigorous)
                else None,
            },
        }

    return await execute_guarded_tool(operation)
