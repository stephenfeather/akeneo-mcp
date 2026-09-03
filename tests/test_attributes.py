"""Regression tests for listing catalog attributes."""

import asyncio
from typing import Any

from akeneo_mcp.akeneo import AkeneoClient
from akeneo_mcp.config import Settings
from akeneo_mcp.server import list_attributes


class _JsonResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


def _settings() -> Settings:
    return Settings(
        akeneo_base_url="https://akeneo.example.test",
        akeneo_client_id="client-id",
        akeneo_client_secret="client-secret",
        akeneo_username="username",
        akeneo_password="password",
    )


def test_list_attributes_parses_nonempty_collection_and_documents_public_shape(monkeypatch):
    observed: dict[str, Any] = {}

    response_body = {
        "_links": {
            "self": {"href": "https://akeneo.example.test/api/rest/v1/attributes?page=1"},
            "first": {"href": "https://akeneo.example.test/api/rest/v1/attributes?page=1"},
            "next": {"href": "https://akeneo.example.test/api/rest/v1/attributes?page=2"},
        },
        "items_count": 27,
        "_embedded": {
            "items": [
                {
                    "code": "name",
                    "type": "pim_catalog_text",
                    "group": "marketing",
                    "labels": {"en_US": "Name"},
                    "localizable": True,
                    "scopable": True,
                    "unique": False,
                    "available_locales": [],
                },
                {
                    "code": "primary_supplier",
                    "type": "pim_catalog_simpleselect",
                    "group": "product",
                    "labels": {"en_US": "Primary supplier"},
                    "localizable": False,
                    "scopable": False,
                    "unique": False,
                    "available_locales": [],
                },
            ]
        },
    }

    async def run_list_attributes() -> dict[str, Any]:
        client = AkeneoClient(_settings())

        async def fake_request(
            method: str,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            **_: Any,
        ) -> _JsonResponse:
            observed.update(method=method, path=path, params=params)
            return _JsonResponse(response_body)

        monkeypatch.setattr(client, "request", fake_request)
        try:
            return await client.list_attributes(limit=500, page=0)
        finally:
            await client.close()

    result = asyncio.run(run_list_attributes())

    assert observed == {
        "method": "GET",
        "path": "/attributes",
        "params": {"limit": 100, "page": 1},
    }
    assert result == {
        "items": [
            {
                "code": "name",
                "type": "pim_catalog_text",
                "group": "marketing",
                "labels": {"en_US": "Name"},
                "localizable": True,
                "scopable": True,
                "unique": False,
            },
            {
                "code": "primary_supplier",
                "type": "pim_catalog_simpleselect",
                "group": "product",
                "labels": {"en_US": "Primary supplier"},
                "localizable": False,
                "scopable": False,
                "unique": False,
            },
        ],
        "count": 2,
        "total_count": 27,
        "next": "https://akeneo.example.test/api/rest/v1/attributes?page=2",
        "previous": None,
    }
    assert "top-level `items`" in (list_attributes.__doc__ or "")
