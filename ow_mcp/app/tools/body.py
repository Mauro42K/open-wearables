"""Remote MCP tool for body summary metrics."""

from fastmcp import FastMCP

from app.services.backend_client import ResourceNotFoundError
from app.services.tool_execution_guard import ToolExecutionContext, execute_guarded_tool

body_router = FastMCP(name="Body Tools")


@body_router.tool
async def get_body_summary(
    user_id: str,
    average_period: int = 7,
    latest_window_hours: int = 4,
) -> dict:
    """Get body summary metrics for a user."""

    async def operation(context: ToolExecutionContext) -> dict:
        try:
            user_data = await context.api_client.get_user(user_id)
        except ResourceNotFoundError:
            return {"error": "unexpected_error", "message": "User not found."}

        body_summary = await context.api_client.get_body_summary(
            user_id=user_id,
            average_period=average_period,
            latest_window_hours=latest_window_hours,
        )

        if body_summary is None:
            return {
                "user": {
                    "id": str(user_data.get("id")),
                    "first_name": user_data.get("first_name"),
                    "last_name": user_data.get("last_name"),
                },
                "summary": None,
                "message": "No body summary data found for this user.",
            }

        source = body_summary.get("source", {})
        slow_changing = body_summary.get("slow_changing", {})
        averaged = body_summary.get("averaged", {})
        latest = body_summary.get("latest", {})

        return {
            "user": {
                "id": str(user_data.get("id")),
                "first_name": user_data.get("first_name"),
                "last_name": user_data.get("last_name"),
            },
            "summary": {
                "source": {
                    "provider": source.get("provider"),
                    "device": source.get("device"),
                }
                if source
                else None,
                "slow_changing": {
                    "weight_kg": slow_changing.get("weight_kg"),
                    "height_cm": slow_changing.get("height_cm"),
                    "body_fat_percent": slow_changing.get("body_fat_percent"),
                    "muscle_mass_kg": slow_changing.get("muscle_mass_kg"),
                    "bmi": slow_changing.get("bmi"),
                    "age": slow_changing.get("age"),
                },
                "averaged": {
                    "period_days": averaged.get("period_days"),
                    "resting_heart_rate_bpm": averaged.get("resting_heart_rate_bpm"),
                    "avg_hrv_sdnn_ms": averaged.get("avg_hrv_sdnn_ms"),
                    "period_start": averaged.get("period_start"),
                    "period_end": averaged.get("period_end"),
                },
                "latest": {
                    "body_temperature_celsius": latest.get("body_temperature_celsius"),
                    "body_temperature_measured_at": latest.get("body_temperature_measured_at"),
                    "skin_temperature_celsius": latest.get("skin_temperature_celsius"),
                    "skin_temperature_measured_at": latest.get("skin_temperature_measured_at"),
                    "blood_pressure": latest.get("blood_pressure"),
                    "blood_pressure_measured_at": latest.get("blood_pressure_measured_at"),
                },
            },
        }

    return await execute_guarded_tool(operation)
