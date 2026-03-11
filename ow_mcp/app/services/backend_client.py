"""HTTP client for ow-api calls."""

import httpx
from typing import Any

from app.config import settings


class InvalidApiKeyError(Exception):
    """Raised when ow-api rejects the provided API key."""


class UpstreamUnavailableError(Exception):
    """Raised when ow-api cannot be reached reliably."""


class ResourceNotFoundError(Exception):
    """Raised when the requested ow-api resource does not exist."""


class OwApiClient:
    """Small client for calling Open Wearables APIs with a specific API key."""

    def __init__(self, api_key: str, base_url: str | None = None) -> None:
        self.api_key = api_key
        self.base_url = (base_url or settings.ow_api_base_url).rstrip("/")
        self.timeout = settings.request_timeout

    @property
    def headers(self) -> dict[str, str]:
        """Headers for ow-api requests."""
        return {
            "X-Open-Wearables-API-Key": self.api_key,
            "Content-Type": "application/json",
        }

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        """Execute an authenticated request against ow-api."""
        url = f"{self.base_url}{path}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, headers=self.headers, **kwargs)
        except httpx.HTTPError as exc:
            raise UpstreamUnavailableError from exc

        if response.status_code in {401, 403}:
            raise InvalidApiKeyError
        if response.status_code == 404:
            raise ResourceNotFoundError
        if response.status_code >= 500:
            raise UpstreamUnavailableError
        response.raise_for_status()
        return response.json()

    async def validate_api_key(self) -> None:
        """Validate an ow-api key against a stable read-only endpoint."""
        await self._request("GET", "/api/v1/users", params={"limit": 1})

    async def get_users(self, search: str | None = None, limit: int = 10) -> dict[str, Any]:
        """Fetch users accessible with the configured API key."""
        params: dict[str, Any] = {"limit": limit}
        if search:
            params["search"] = search
        return await self._request("GET", "/api/v1/users", params=params)

    async def get_user(self, user_id: str) -> dict[str, Any]:
        """Fetch a specific user."""
        return await self._request("GET", f"/api/v1/users/{user_id}")

    async def get_activity_summaries(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch activity summaries for a user within a date range."""
        return await self._request(
            "GET",
            f"/api/v1/users/{user_id}/summaries/activity",
            params={
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            },
        )

    async def get_sleep_summaries(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch sleep summaries for a user within a date range."""
        return await self._request(
            "GET",
            f"/api/v1/users/{user_id}/summaries/sleep",
            params={
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            },
        )

    async def get_sleep_sessions(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch sleep sessions for a user within a date range."""
        return await self._request(
            "GET",
            f"/api/v1/users/{user_id}/events/sleep",
            params={
                "start_date": start_date,
                "end_date": end_date,
                "limit": limit,
            },
        )

    async def get_workouts(
        self,
        user_id: str,
        start_date: str,
        end_date: str,
        record_type: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """Fetch workouts for a user within a date range."""
        params: dict[str, Any] = {
            "start_date": start_date,
            "end_date": end_date,
            "limit": limit,
        }
        if record_type:
            params["record_type"] = record_type

        return await self._request(
            "GET",
            f"/api/v1/users/{user_id}/events/workouts",
            params=params,
        )

    async def get_body_summary(
        self,
        user_id: str,
        average_period: int = 7,
        latest_window_hours: int = 4,
    ) -> dict[str, Any] | None:
        """Fetch body summary metrics for a user."""
        return await self._request(
            "GET",
            f"/api/v1/users/{user_id}/summaries/body",
            params={
                "average_period": average_period,
                "latest_window_hours": latest_window_hours,
            },
        )

    async def get_timeseries(
        self,
        user_id: str,
        start_time: str,
        end_time: str,
        types: list[str],
        resolution: str = "raw",
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Fetch selected timeseries samples for a user."""
        params: dict[str, Any] = {
            "start_time": start_time,
            "end_time": end_time,
            "types": types,
            "resolution": resolution,
            "limit": limit,
        }
        if cursor:
            params["cursor"] = cursor

        return await self._request(
            "GET",
            f"/api/v1/users/{user_id}/timeseries",
            params=params,
        )


def create_ow_api_client(api_key: str) -> OwApiClient:
    """Create a request-scoped ow-api client."""
    return OwApiClient(api_key=api_key, base_url="https://ow-api.mauro42k.com")
