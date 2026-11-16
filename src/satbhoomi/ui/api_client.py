"""HTTP API client for SatBhoomi Streamlit frontend (S1 to S4).

Communicates strictly over HTTP with FastAPI backend endpoints.
Guarantees:
- Zero password, credential, or bearer token logging.
- Typed ApiError with standard error payload mapping.
- 401 responses mapped to SessionExpiredError.
- Explicit timeouts on every network call.
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import httpx

logger = logging.getLogger("satbhoomi.ui.api_client")

DEFAULT_API_BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT_SECONDS = 10.0


class ApiError(Exception):
    """Structured error returned by the SatBhoomi REST API."""

    def __init__(
        self,
        message: str,
        code: str = "API_ERROR",
        field: str | None = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.field = field
        self.status_code = status_code

    def __str__(self) -> str:
        if self.field:
            return f"[{self.code}] {self.message} (field: {self.field})"
        return f"[{self.code}] {self.message}"


class SessionExpiredError(ApiError):
    """Raised when an API call returns 401 Unauthorized."""

    def __init__(self, message: str = "Your session has ended. Please sign in again.") -> None:
        super().__init__(message=message, code="UNAUTHORIZED", status_code=401)


class ApiClient:
    """Lightweight HTTP client talking to the SatBhoomi API."""

    def __init__(
        self,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = (base_url or os.getenv("SATBHOOMI_API_URL") or DEFAULT_API_BASE_URL).rstrip(
            "/"
        )
        self.timeout = timeout

    def _headers(
        self, token: str | None = None, idempotency_key: str | None = None
    ) -> dict[str, str]:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    def _parse_error_response(self, response: httpx.Response) -> ApiError:
        status_code = response.status_code
        if status_code == 401:
            return SessionExpiredError()

        code = "HTTP_ERROR"
        message = f"Request failed with HTTP {status_code}"
        field: str | None = None

        try:
            payload = response.json()
            if isinstance(payload, dict):
                if "error" in payload and isinstance(payload["error"], dict):
                    err = payload["error"]
                    code = str(err.get("code", code))
                    message = str(err.get("message", message))
                    field = err.get("field")
                elif "detail" in payload:
                    message = str(payload["detail"])
        except Exception:
            pass

        return ApiError(message=message, code=code, field=field, status_code=status_code)

    def login(self, username: str, password: str) -> dict[str, Any]:
        """Authenticate user credentials and receive JWT access token.

        Never logs username, password, or the returned token.
        """
        url = f"{self.base_url}/api/v1/auth/login"
        payload = {"username": username, "password": password}

        logger.info("Sending login request to backend")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=self._headers())
        except httpx.RequestError as exc:
            logger.error("Network failure during login call: %s", type(exc).__name__)
            raise ApiError(
                f"Unable to connect to server: {exc}", code="NETWORK_ERROR", status_code=503
            ) from exc

        if resp.status_code != 200:
            logger.warning("Login failed with status %d", resp.status_code)
            raise self._parse_error_response(resp)

        logger.info("Login succeeded with status 200")
        return resp.json()

    def list_plots(
        self,
        token: str,
        limit: int = 10,
        offset: int = 0,
        district: str | None = None,
    ) -> dict[str, Any]:
        """Fetch paginated plot list with optional district filter."""
        url = f"{self.base_url}/api/v1/plots"
        params: dict[str, Any] = {"limit": min(limit, 100), "offset": max(0, offset)}
        if district and district.strip() and district != "All Districts":
            params["district"] = district.strip()

        logger.info("Listing plots (limit=%d, offset=%d)", limit, offset)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params, headers=self._headers(token=token))
        except httpx.RequestError as exc:
            logger.error("Network failure during list_plots: %s", type(exc).__name__)
            raise ApiError(f"Network error: {exc}", code="NETWORK_ERROR", status_code=503) from exc

        if resp.status_code != 200:
            raise self._parse_error_response(resp)

        return resp.json()

    def create_plot(self, plot_data: dict[str, Any], token: str) -> dict[str, Any]:
        """Register a new agricultural plot parcel."""
        url = f"{self.base_url}/api/v1/plots"

        logger.info("Creating new plot")
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=plot_data, headers=self._headers(token=token))
        except httpx.RequestError as exc:
            logger.error("Network failure during create_plot: %s", type(exc).__name__)
            raise ApiError(f"Network error: {exc}", code="NETWORK_ERROR", status_code=503) from exc

        if resp.status_code != 201:
            raise self._parse_error_response(resp)

        return resp.json()

    def create_assessment(
        self,
        plot_id: int,
        token: str,
        season: str = "2024-25",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Trigger an in-season crop risk assessment for a plot."""
        url = f"{self.base_url}/api/v1/plots/{plot_id}/assessments"
        key = idempotency_key or f"ui-eval-{uuid.uuid4().hex[:16]}"
        payload = {"season": season}

        logger.info("Requesting assessment for plot_id=%d, season=%s", plot_id, season)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    url,
                    json=payload,
                    headers=self._headers(token=token, idempotency_key=key),
                )
        except httpx.RequestError as exc:
            logger.error("Network failure during create_assessment: %s", type(exc).__name__)
            raise ApiError(f"Network error: {exc}", code="NETWORK_ERROR", status_code=503) from exc

        if resp.status_code != 201:
            raise self._parse_error_response(resp)

        return resp.json()

    def get_assessment(self, assessment_id: int, token: str) -> dict[str, Any]:
        """Retrieve existing risk assessment by ID."""
        url = f"{self.base_url}/api/v1/assessments/{assessment_id}"

        logger.info("Retrieving assessment id=%d", assessment_id)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._headers(token=token))
        except httpx.RequestError as exc:
            logger.error("Network failure during get_assessment: %s", type(exc).__name__)
            raise ApiError(f"Network error: {exc}", code="NETWORK_ERROR", status_code=503) from exc

        if resp.status_code != 200:
            raise self._parse_error_response(resp)

        return resp.json()

    def run_what_if(
        self,
        assessment_id: int,
        changed_input: str,
        new_value: str,
        token: str,
    ) -> dict[str, Any]:
        """Project score and limit variations under a hypothetical farm intervention."""
        url = f"{self.base_url}/api/v1/assessments/{assessment_id}/what-if"
        payload = {"changed_input": changed_input, "new_value": new_value}

        logger.info(
            "Running what-if on assessment=%d (input=%s, val=%s)",
            assessment_id,
            changed_input,
            new_value,
        )
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=self._headers(token=token))
        except httpx.RequestError as exc:
            logger.error("Network failure during run_what_if: %s", type(exc).__name__)
            raise ApiError(f"Network error: {exc}", code="NETWORK_ERROR", status_code=503) from exc

        if resp.status_code != 200:
            raise self._parse_error_response(resp)

        return resp.json()

    def get_monitoring(
        self,
        plot_id: int,
        token: str,
        season: str | None = None,
    ) -> dict[str, Any]:
        """Fetch historical monitoring replay timeline and in-season alerts for a plot."""
        url = f"{self.base_url}/api/v1/plots/{plot_id}/monitoring"
        params: dict[str, Any] = {}
        if season and season.strip():
            params["season"] = season.strip()

        logger.info("Fetching monitoring for plot_id=%d, season=%s", plot_id, season)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params or None, headers=self._headers(token=token))
        except httpx.RequestError as exc:
            logger.error("Network failure during get_monitoring: %s", type(exc).__name__)
            raise ApiError(f"Network error: {exc}", code="NETWORK_ERROR", status_code=503) from exc

        if resp.status_code != 200:
            raise self._parse_error_response(resp)

        return resp.json()

    def record_alert_action(
        self,
        alert_id: int,
        action_type: str,
        note: str,
        token: str,
    ) -> dict[str, Any]:
        """Record an officer intervention from the supportive playbook for an alert."""
        url = f"{self.base_url}/api/v1/alerts/{alert_id}/actions"
        payload = {"action_type": action_type, "note": note}

        logger.info("Logging alert action on alert_id=%d, action=%s", alert_id, action_type)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(url, json=payload, headers=self._headers(token=token))
        except httpx.RequestError as exc:
            logger.error("Network failure during record_alert_action: %s", type(exc).__name__)
            raise ApiError(f"Network error: {exc}", code="NETWORK_ERROR", status_code=503) from exc

        if resp.status_code != 201:
            raise self._parse_error_response(resp)

        return resp.json()

    def get_relief_report(self, plot_id: int, token: str) -> dict[str, Any]:
        """Fetch RBI 33% calamity relief screening evidence report."""
        url = f"{self.base_url}/api/v1/plots/{plot_id}/relief-report"

        logger.info("Fetching relief report for plot_id=%d", plot_id)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, headers=self._headers(token=token))
        except httpx.RequestError as exc:
            logger.error("Network failure during get_relief_report: %s", type(exc).__name__)
            raise ApiError(f"Network error: {exc}", code="NETWORK_ERROR", status_code=503) from exc

        if resp.status_code != 200:
            raise self._parse_error_response(resp)

        return resp.json()

    def get_farmer_summary(
        self,
        assessment_id: int,
        token: str,
        lang: str = "en",
    ) -> dict[str, Any]:
        """Fetch vernacular credit assessment summary in English, Gujarati, or Hindi."""
        url = f"{self.base_url}/api/v1/assessments/{assessment_id}/farmer-summary"
        params = {"lang": lang.lower()}

        logger.info("Fetching farmer summary for assessment=%d, lang=%s", assessment_id, lang)
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(url, params=params, headers=self._headers(token=token))
        except httpx.RequestError as exc:
            logger.error("Network failure during get_farmer_summary: %s", type(exc).__name__)
            raise ApiError(f"Network error: {exc}", code="NETWORK_ERROR", status_code=503) from exc

        if resp.status_code != 200:
            raise self._parse_error_response(resp)

        return resp.json()
