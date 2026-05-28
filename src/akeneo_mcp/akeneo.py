from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any
from urllib.parse import quote

import httpx

from .config import Settings


class AkeneoClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._http = httpx.AsyncClient(
            timeout=settings.akeneo_timeout_seconds,
            verify=settings.akeneo_verify_ssl,
            headers={"Accept": "application/json"},
        )
        self._lock = asyncio.Lock()
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0

    async def close(self) -> None:
        await self._http.aclose()

    @property
    def token_url(self) -> str:
        return f"{self.settings.akeneo_base_url}/api/oauth/v1/token"

    @property
    def api_root(self) -> str:
        return f"{self.settings.akeneo_base_url}/api/rest/v1"

    def _basic_auth_header(self) -> str:
        raw = f"{self.settings.akeneo_client_id}:{self.settings.akeneo_client_secret}".encode()
        return "Basic " + base64.b64encode(raw).decode("ascii")

    def _token_valid(self) -> bool:
        return bool(self._access_token) and time.time() < (self._expires_at - 30)

    async def _exchange_password_grant(self) -> None:
        response = await self._http.post(
            self.token_url,
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/json",
            },
            json={
                "grant_type": "password",
                "username": self.settings.akeneo_username,
                "password": self.settings.akeneo_password,
            },
        )
        response.raise_for_status()
        self._store_tokens(response.json())

    async def _exchange_refresh_token(self) -> None:
        if not self._refresh_token:
            raise RuntimeError("No refresh token available")
        response = await self._http.post(
            self.token_url,
            headers={
                "Authorization": self._basic_auth_header(),
                "Content-Type": "application/json",
            },
            json={
                "grant_type": "refresh_token",
                "refresh_token": self._refresh_token,
            },
        )
        response.raise_for_status()
        self._store_tokens(response.json())

    def _store_tokens(self, payload: dict[str, Any]) -> None:
        self._access_token = payload["access_token"]
        self._refresh_token = payload.get("refresh_token")
        self._expires_at = time.time() + int(payload.get("expires_in", 3600))

    async def ensure_access_token(self, *, force_refresh: bool = False) -> str:
        async with self._lock:
            if not force_refresh and self._token_valid():
                return self._access_token or ""

            if force_refresh and self._refresh_token:
                try:
                    await self._exchange_refresh_token()
                    return self._access_token or ""
                except httpx.HTTPError:
                    self._refresh_token = None

            if self._refresh_token and not force_refresh:
                try:
                    await self._exchange_refresh_token()
                    return self._access_token or ""
                except httpx.HTTPError:
                    self._refresh_token = None

            await self._exchange_password_grant()
            return self._access_token or ""

    async def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        retry_on_401: bool = True,
    ) -> httpx.Response:
        token = await self.ensure_access_token()
        response = await self._http.request(
            method,
            f"{self.api_root}{path}",
            params=params,
            json=json_body,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 401 and retry_on_401:
            token = await self.ensure_access_token(force_refresh=True)
            response = await self._http.request(
                method,
                f"{self.api_root}{path}",
                params=params,
                json=json_body,
                headers={"Authorization": f"Bearer {token}"},
            )
        response.raise_for_status()
        return response

    async def healthcheck(self) -> dict[str, Any]:
        response = await self.request("GET", "")
        body = response.json()
        routes = sorted((body.get("routes") or {}).keys())
        return {
            "reachable": True,
            "base_url": self.settings.akeneo_base_url,
            "authentication": body.get("authentication", {}),
            "route_count": len(routes),
            "sample_routes": routes[:10],
        }

    async def search_products(
        self,
        *,
        family: str | None = None,
        enabled: bool | None = None,
        categories_any: list[str] | None = None,
        limit: int = 10,
        page: int = 1,
        raw_search_json: str | None = None,
    ) -> dict[str, Any]:
        search: dict[str, list[dict[str, Any]]] = {}
        if family:
            search["family"] = [{"operator": "IN", "value": [family]}]
        if enabled is not None:
            search["enabled"] = [{"operator": "=", "value": enabled}]
        if categories_any:
            search["categories"] = [{"operator": "IN", "value": categories_any}]
        if raw_search_json:
            extra = json.loads(raw_search_json)
            if not isinstance(extra, dict):
                raise ValueError("raw_search_json must decode to a JSON object")
            search.update(extra)

        params: dict[str, Any] = {
            "limit": max(1, min(limit, 100)),
            "page": max(1, page),
            "pagination_type": "page",
        }
        if search:
            params["search"] = json.dumps(search, separators=(",", ":"))

        response = await self.request("GET", "/products-uuid", params=params)
        body = response.json()
        return {
            "filters_used": search,
            "endpoint": "/products-uuid",
            "count": body.get("current_item_count", 0),
            "items": [
                self._summarize_product(item) for item in body.get("_embedded", {}).get("items", [])
            ],
            "next": body.get("_links", {}).get("next", {}).get("href"),
            "previous": body.get("_links", {}).get("previous", {}).get("href"),
        }

    async def get_product(self, identifier: str) -> dict[str, Any]:
        response = await self.request("GET", f"/products/{quote(identifier, safe='')}")
        payload = self._summarize_product_detail(response.json())
        payload["endpoint"] = "/products/{identifier}"
        return payload

    async def get_product_by_uuid(self, uuid: str) -> dict[str, Any]:
        response = await self.request("GET", f"/products-uuid/{quote(uuid, safe='')}")
        payload = self._summarize_product_detail(response.json())
        payload["endpoint"] = "/products-uuid/{uuid}"
        return payload

    async def list_families(self, *, limit: int = 50, page: int = 1) -> dict[str, Any]:
        response = await self.request(
            "GET", "/families", params={"limit": max(1, min(limit, 100)), "page": max(1, page)}
        )
        body = response.json()
        items = body.get("_embedded", {}).get("items", [])
        return {
            "count": body.get("current_item_count", len(items)),
            "items": [self._summarize_family(item) for item in items],
            "next": body.get("_links", {}).get("next", {}).get("href"),
            "previous": body.get("_links", {}).get("previous", {}).get("href"),
        }

    async def get_family(self, code: str) -> dict[str, Any]:
        response = await self.request("GET", f"/families/{quote(code, safe='')}")
        return self._summarize_family(response.json(), include_attributes=True)

    async def list_attributes(self, *, limit: int = 50, page: int = 1) -> dict[str, Any]:
        response = await self.request(
            "GET", "/attributes", params={"limit": max(1, min(limit, 100)), "page": max(1, page)}
        )
        body = response.json()
        items = body.get("_embedded", {}).get("items", [])
        return {
            "count": body.get("current_item_count", len(items)),
            "items": [self._summarize_attribute(item) for item in items],
            "next": body.get("_links", {}).get("next", {}).get("href"),
            "previous": body.get("_links", {}).get("previous", {}).get("href"),
        }

    async def get_attribute(self, code: str) -> dict[str, Any]:
        response = await self.request("GET", f"/attributes/{quote(code, safe='')}")
        return self._summarize_attribute(response.json(), detailed=True)

    async def list_categories(self, *, limit: int = 50, page: int = 1) -> dict[str, Any]:
        response = await self.request(
            "GET", "/categories", params={"limit": max(1, min(limit, 100)), "page": max(1, page)}
        )
        body = response.json()
        items = body.get("_embedded", {}).get("items", [])
        return {
            "count": body.get("current_item_count", len(items)),
            "items": [self._summarize_category(item) for item in items],
            "next": body.get("_links", {}).get("next", {}).get("href"),
            "previous": body.get("_links", {}).get("previous", {}).get("href"),
        }

    async def get_category(self, code: str) -> dict[str, Any]:
        response = await self.request("GET", f"/categories/{quote(code, safe='')}")
        return self._summarize_category(response.json(), detailed=True)

    @staticmethod
    def _summarize_product(item: dict[str, Any]) -> dict[str, Any]:
        values = item.get("values") or {}
        label = None
        for key in ("name", "title", "label"):
            if values.get(key):
                candidate = values[key][0].get("data")
                if isinstance(candidate, str) and candidate.strip():
                    label = candidate.strip()
                    break
        return {
            "identifier": item.get("identifier"),
            "uuid": item.get("uuid"),
            "label": label,
            "family": item.get("family"),
            "enabled": item.get("enabled"),
            "categories": item.get("categories", []),
            "value_count": len(values),
        }

    @staticmethod
    def _summarize_product_detail(item: dict[str, Any]) -> dict[str, Any]:
        values = item.get("values") or {}
        summarized_values: dict[str, Any] = {}
        for index, (code, entries) in enumerate(values.items()):
            if index >= 40:
                break
            summarized_values[code] = entries
        return {
            "identifier": item.get("identifier"),
            "uuid": item.get("uuid"),
            "family": item.get("family"),
            "enabled": item.get("enabled"),
            "categories": item.get("categories", []),
            "groups": item.get("groups", []),
            "associations": item.get("associations", {}),
            "metadata": item.get("metadata", {}),
            "values": summarized_values,
            "truncated_value_count": max(0, len(values) - len(summarized_values)),
        }

    @staticmethod
    def _summarize_family(
        item: dict[str, Any], *, include_attributes: bool = False
    ) -> dict[str, Any]:
        payload = {
            "code": item.get("code"),
            "labels": item.get("labels", {}),
            "attribute_as_label": item.get("attribute_as_label"),
            "attribute_as_image": item.get("attribute_as_image"),
        }
        if include_attributes:
            payload["attributes"] = item.get("attributes", [])
        return payload

    @staticmethod
    def _summarize_attribute(item: dict[str, Any], *, detailed: bool = False) -> dict[str, Any]:
        payload = {
            "code": item.get("code"),
            "type": item.get("type"),
            "group": item.get("group"),
            "labels": item.get("labels", {}),
            "localizable": item.get("localizable"),
            "scopable": item.get("scopable"),
            "unique": item.get("unique"),
        }
        if detailed:
            payload.update(
                {
                    "available_locales": item.get("available_locales", []),
                    "metric_family": item.get("metric_family"),
                    "default_metric_unit": item.get("default_metric_unit"),
                    "options": item.get("options", []),
                    "reference_data_name": item.get("reference_data_name"),
                }
            )
        return payload

    @staticmethod
    def _summarize_category(item: dict[str, Any], *, detailed: bool = False) -> dict[str, Any]:
        payload = {
            "code": item.get("code"),
            "parent": item.get("parent"),
            "labels": item.get("labels", {}),
        }
        if detailed:
            payload.update({"values": item.get("values", {})})
        return payload
