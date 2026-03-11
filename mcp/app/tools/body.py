"""MCP tools for querying body summary metrics."""

import logging

from fastmcp import FastMCP

from app.services.api_client import client

logger = logging.getLogger(__name__)

# Create router for body-related tools
body_router = FastMCP(name="Body Tools")


@body_router.tool
async def get_body_summary(
    user_id: str,
    average_period: int = 7,
    latest_window_hours: int = 4,
) -> dict:
    """
    Get body metrics summary for a user.

    This tool retrieves body composition and vitals grouped into:
    - slow_changing: latest weight, height, body fat, muscle mass, BMI, age
    - averaged: resting heart rate and HRV averaged over 1-7 days
    - latest: recent body temperature, skin temperature, and blood pressure

    Args:
        user_id: UUID of the user. Use get_users to discover available users.
        average_period: Days to average vitals (1-7, default 7).
        latest_window_hours: Hours for point-in-time readings to be considered recent (1-24, default 4).

    Returns:
        A dictionary containing:
        - user: Information about the user (id, first_name, last_name)
        - summary: Body summary grouped into slow_changing, averaged, and latest

    Notes for LLMs:
        - Call get_users first to get the user_id.
        - Use average_period=7 for baseline trends and average_period=1 for current-day state.
        - Many point-in-time metrics may be null if the wearable/source does not provide them
          or if the latest readings fall outside latest_window_hours.
        - The backend returns null if no body data exists for the user.
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

        body_summary = await client.get_body_summary(
            user_id=user_id,
            average_period=average_period,
            latest_window_hours=latest_window_hours,
        )

        if body_summary is None:
            return {
                "user": user,
                "summary": None,
                "message": "No body summary data found for this user.",
            }

        source = body_summary.get("source", {})
        slow_changing = body_summary.get("slow_changing", {})
        averaged = body_summary.get("averaged", {})
        latest = body_summary.get("latest", {})

        return {
            "user": user,
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

    except ValueError as e:
        logger.error(f"API error in get_body_summary: {e}")
        return {"error": str(e)}
    except Exception as e:
        logger.exception(f"Unexpected error in get_body_summary: {e}")
        return {"error": f"Failed to fetch body summary: {e}"}
