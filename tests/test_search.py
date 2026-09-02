"""Tests for product search input validation and request serialization."""

import asyncio
from typing import Any

import pytest
from pydantic import ValidationError

from akeneo_mcp.akeneo import AkeneoClient
from akeneo_mcp.config import Settings
from akeneo_mcp.server import explain_product_search_json, mcp


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


def _run_client_search(
    monkeypatch,
    raw_search_json: str | dict[str, Any] | list[Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    observed: dict[str, Any] = {}

    async def run_search() -> dict[str, Any]:
        client = AkeneoClient(_settings())

        async def fake_request(
            method: str,
            path: str,
            *,
            params: dict[str, Any] | None = None,
            **_: Any,
        ) -> _JsonResponse:
            observed.update(method=method, path=path, params=params)
            return _JsonResponse({"_embedded": {"items": []}, "_links": {}})

        monkeypatch.setattr(client, "request", fake_request)
        try:
            return await client.search_products(raw_search_json=raw_search_json)  # type: ignore[arg-type]
        finally:
            await client.close()

    return observed, asyncio.run(run_search())


def test_search_products_schema_accepts_object_string_or_null():
    tool = mcp._tool_manager.get_tool("search_products")
    raw_search_schema = tool.parameters["properties"]["raw_search_json"]

    variants = raw_search_schema["anyOf"]
    assert {variant["type"] for variant in variants} == {"object", "string", "null"}
    assert (
        next(variant for variant in variants if variant["type"] == "object")["additionalProperties"]
        is True
    )


def test_structured_search_is_serialized_once_with_simple_select_in_shape(monkeypatch):
    raw_search = {
        "primary_supplier": [{"operator": "IN", "value": ["davidsons"]}],
    }
    observed, result = _run_client_search(monkeypatch, raw_search)

    assert observed == {
        "method": "GET",
        "path": "/products-uuid",
        "params": {
            "limit": 10,
            "page": 1,
            "pagination_type": "page",
            "search": '{"primary_supplier":[{"operator":"IN","value":["davidsons"]}]}',
        },
    }
    assert result["filters_used"] == raw_search


def test_legacy_serialized_search_string_still_works(monkeypatch):
    raw_search = '{"primary_supplier":[{"operator":"IN","value":["davidsons"]}]}'

    observed, result = _run_client_search(monkeypatch, raw_search)

    assert observed["params"]["search"] == raw_search
    assert result["filters_used"] == {
        "primary_supplier": [{"operator": "IN", "value": ["davidsons"]}],
    }


def test_serialized_json_list_is_rejected(monkeypatch):
    with pytest.raises(ValueError, match="raw_search_json must decode to a JSON object"):
        _run_client_search(monkeypatch, '[{"operator":"IN","value":["davidsons"]}]')


def test_fastmcp_rejects_direct_list_input():
    tool = mcp._tool_manager.get_tool("search_products")

    with pytest.raises(ValidationError, match="raw_search_json"):
        tool.fn_metadata.arg_model.model_validate(
            {"raw_search_json": [{"operator": "IN", "value": ["davidsons"]}]}
        )


def test_search_help_prefers_objects_and_documents_legacy_strings():
    reference = asyncio.run(explain_product_search_json())

    usage = reference["usage"].lower()
    assert "object" in usage
    assert "preferred" in usage
    assert "string" in usage
    assert "backward" in usage
