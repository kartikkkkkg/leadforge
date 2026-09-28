"""HttpApiProvider: skeleton for a legitimate external company-data API.

This is the production extension point — not a working integration. No
specific third-party provider is required by DESIGN.md, so there is no
hardcoded endpoint contract here. What IS real:

* configuration shape (base URL, API key, timeout) from the environment,
* the request/response plumbing with safe error handling,
* credential hygiene (never logged, never in error messages, never in repr),
* honest health reporting (``not_configured`` / ``available`` / ``error``).

To attach a real API: implement the two marked integration points
(``_search_path`` / ``_map_search_response`` and ``_details_path`` /
``_map_details_response``) for that API's endpoint contract. No scraping,
no bot evasion, no login-wall bypassing — legitimate APIs only.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..config import get_settings
from ..schemas import ProviderHealth
from .base import (
    CompanyQuery,
    ContactInfo,
    NotConfiguredError,
    ProviderError,
    RawCompany,
    ResearchProvider,
)

log = logging.getLogger(__name__)

_CONFIGURE_INSTRUCTIONS = (
    "HttpApiProvider is not configured. Set LEADFORGE_HTTP_API_BASE_URL "
    "(e.g. https://api.example-provider.com) and LEADFORGE_HTTP_API_KEY, "
    "then retry."
)


class HttpApiProvider(ResearchProvider):
    """Config-gated HTTP provider skeleton."""

    name = "http"

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: float | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url if base_url is not None else settings.leadforge_http_api_base_url) or None
        self._api_key = (api_key if api_key is not None else settings.leadforge_http_api_key) or None
        self._timeout_s = timeout_s if timeout_s is not None else settings.leadforge_http_timeout_s
        if self._base_url:
            self._base_url = self._base_url.rstrip("/")

    def __repr__(self) -> str:
        # Never expose the API key.
        return (
            f"{type(self).__name__}(base_url={self._base_url!r}, "
            f"api_key={'***' if self._api_key else None}, timeout_s={self._timeout_s!r})"
        )

    @property
    def is_configured(self) -> bool:
        """True only when both base URL and API key are present."""
        return bool(self._base_url and self._api_key)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": "LeadForge/0.1"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _request(
        self, method: str, path: str, params: dict[str, Any] | None = None
    ) -> Any:
        """Low-level request abstraction with predictable errors.

        Raises :class:`ProviderError` (never leaks credentials) on timeouts,
        connection failures, HTTP errors, and bad payloads.
        """
        assert self._base_url, "HttpApiProvider._request requires a base URL"
        url = self._base_url + path
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        request = urllib.request.Request(url, headers=self._headers(), method=method)
        log.debug("HTTP %s %s", method, url.split("?")[0])  # path only; never query/headers
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_s) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            raise ProviderError(f"provider returned HTTP {exc.code}") from exc
        except urllib.error.URLError as exc:
            raise ProviderError(f"provider unreachable: {exc.reason}") from exc
        except TimeoutError as exc:
            raise ProviderError(f"provider request timed out after {self._timeout_s}s") from exc
        except OSError as exc:  # socket-level failures
            raise ProviderError(f"provider request failed: {exc}") from exc
        try:
            return json.loads(body) if body.strip() else None
        except json.JSONDecodeError as exc:
            raise ProviderError("provider returned a non-JSON response") from exc

    # -- integration points: attach a legitimate API's contract here --------

    def _search_path(self, query: CompanyQuery) -> tuple[str, dict[str, Any]]:
        """Return ``(path, params)`` for the provider's company-search endpoint."""
        # INTEGRATION POINT: replace with the real API's search endpoint,
        # e.g. return ("/v1/companies/search", {"industry": query.industry, ...}).
        return ("/companies/search", {"industry": query.industry, "country": query.country})

    def _details_path(self, ref: str) -> str:
        """Return the path for the provider's company-details endpoint."""
        # INTEGRATION POINT: replace with the real API's details endpoint.
        return f"/companies/{urllib.parse.quote(ref)}"

    # -- ResearchProvider interface ------------------------------------------

    async def search_companies(self, query: CompanyQuery, limit: int) -> list[RawCompany]:
        if not self.is_configured:
            raise NotConfiguredError(_CONFIGURE_INSTRUCTIONS)
        path, params = self._search_path(query)
        params = {**params, "limit": limit}
        payload = self._request("GET", path, params)
        # INTEGRATION POINT: map the real API's response items to RawCompany
        # fields here. The defensive default accepts a list of field dicts.
        items = payload if isinstance(payload, list) else (payload or {}).get("items", [])
        if not isinstance(items, list):
            raise ProviderError("provider returned an unexpected search payload")
        return [RawCompany(**item) for item in items if isinstance(item, dict)][:limit]

    async def get_company_details(self, ref: str) -> RawCompany | None:
        if not self.is_configured:
            raise NotConfiguredError(_CONFIGURE_INSTRUCTIONS)
        payload = self._request("GET", self._details_path(ref))
        if payload is None:
            return None
        # INTEGRATION POINT: map the real API's details response here.
        if not isinstance(payload, dict):
            raise ProviderError("provider returned an unexpected details payload")
        return RawCompany(**payload)

    def extract_contacts(self, raw: RawCompany) -> ContactInfo:
        return ContactInfo(email=raw.public_email, phone=raw.phone)

    def health(self) -> ProviderHealth:
        if not self.is_configured:
            return ProviderHealth(
                name=self.name,
                status="not_configured",
                detail="Set LEADFORGE_HTTP_API_BASE_URL and LEADFORGE_HTTP_API_KEY to enable.",
            )
        # Actual health check: a lightweight request against the base URL.
        # Only a successful response earns "available".
        try:
            self._request("GET", "/")
        except ProviderError as exc:
            return ProviderHealth(name=self.name, status="error", detail=str(exc))
        return ProviderHealth(
            name=self.name, status="available", detail="Provider reachable."
        )
