"""Remote MCP tool for listing users."""

from fastmcp import FastMCP

from app.services.tool_execution_guard import ToolExecutionContext, execute_guarded_tool

users_router = FastMCP(name="Users Tools")


@users_router.tool
async def get_users(search: str | None = None, limit: int = 10) -> dict:
    """Get users accessible via the authenticated user's connected ow-api key."""

    async def operation(context: ToolExecutionContext) -> dict:
        response = await context.api_client.get_users(search=search, limit=limit)
        users = response.get("items", [])
        return {
            "users": [
                {
                    "id": str(user.get("id")),
                    "first_name": user.get("first_name"),
                    "last_name": user.get("last_name"),
                    "email": user.get("email"),
                }
                for user in users
            ],
            "total": response.get("total", len(users)),
        }

    return await execute_guarded_tool(operation)
