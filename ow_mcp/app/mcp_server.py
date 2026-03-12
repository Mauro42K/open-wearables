"""Remote MCP server configuration."""

from fastmcp import FastMCP

from app.services.mcp_auth import create_mcp_auth_provider
from app.tools.activity import activity_router
from app.tools.body import body_router
from app.tools.sleep import sleep_router
from app.tools.timeseries import timeseries_router
from app.tools.users import users_router
from app.tools.workouts import workouts_router


def create_mcp_server() -> tuple[FastMCP, object | None]:
    """Build the FastMCP server and its optional OAuth provider."""
    auth_provider = create_mcp_auth_provider()
    mcp = FastMCP(
        "ow-mcp",
        instructions="""
        Remote MCP server for Open Wearables.

        Available tools:
        - get_users: Discover users accessible via the authenticated user's connected Open Wearables API key
        - get_activity_summary: Get daily activity data for a user over a date range
        - get_sleep_summary: Get daily sleep data for a user over a date range
        - get_sleep_sessions: Get sleep sessions and naps for a user over a date range
        - get_workout_events: Get workout sessions for a user over a date range
        - get_body_summary: Get grouped body metrics and vitals for a user
        - get_timeseries: Get selected heart rate and steps timeseries samples for a user

        Before executing tools, this server resolves the authenticated user, loads their stored
        Open Wearables API key, and calls the upstream API on their behalf.
        """,
        auth=auth_provider,
    )

    mcp.mount(users_router)
    mcp.mount(activity_router)
    mcp.mount(sleep_router)
    mcp.mount(workouts_router)
    mcp.mount(body_router)
    mcp.mount(timeseries_router)
    return mcp, auth_provider
