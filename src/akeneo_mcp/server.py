from __future__ import annotations

from functools import lru_cache
from typing import Any

from mcp.server.fastmcp import FastMCP

from .akeneo import AkeneoClient
from .config import Settings

mcp = FastMCP(
    name="Akeneo MCP",
    instructions=(
        "Private-first MCP bridge for Akeneo PIM. Prefer the read-only tools unless write support has been "
        "explicitly enabled and reviewed. Product discovery defaults to Akeneo's UUID endpoints where possible."
    ),
    json_response=True,
    stateless_http=True,
)

_client: AkeneoClient | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


async def get_client() -> AkeneoClient:
    global _client
    if _client is None:
        _client = AkeneoClient(get_settings())
    return _client


@mcp.tool()
async def healthcheck_akeneo() -> dict[str, Any]:
    """Verify connectivity and authentication against the Akeneo REST API root."""
    client = await get_client()
    return await client.healthcheck()


@mcp.tool()
async def search_products(
    family: str | None = None,
    enabled: bool | None = None,
    categories_any: list[str] | None = None,
    limit: int = 10,
    page: int = 1,
    raw_search_json: str | None = None,
) -> dict[str, Any]:
    """Search products via Akeneo's UUID collection endpoint with a small set of common filters plus a raw JSON escape hatch."""
    client = await get_client()
    return await client.search_products(
        family=family,
        enabled=enabled,
        categories_any=categories_any,
        limit=limit,
        page=page,
        raw_search_json=raw_search_json,
    )


@mcp.tool()
async def get_product(identifier: str) -> dict[str, Any]:
    """Fetch a single product by Akeneo identifier (SKU/code)."""
    client = await get_client()
    return await client.get_product(identifier)


@mcp.tool()
async def get_product_by_uuid(uuid: str) -> dict[str, Any]:
    """Fetch a single product by Akeneo UUID. This is the preferred direct lookup when you already have a UUID."""
    client = await get_client()
    return await client.get_product_by_uuid(uuid)


@mcp.tool()
async def list_families(limit: int = 50, page: int = 1) -> dict[str, Any]:
    """List product families."""
    client = await get_client()
    return await client.list_families(limit=limit, page=page)


@mcp.tool()
async def get_family(code: str) -> dict[str, Any]:
    """Fetch a family by code."""
    client = await get_client()
    return await client.get_family(code)


@mcp.tool()
async def list_attributes(limit: int = 50, page: int = 1) -> dict[str, Any]:
    """List catalog attributes."""
    client = await get_client()
    return await client.list_attributes(limit=limit, page=page)


@mcp.tool()
async def get_attribute(code: str) -> dict[str, Any]:
    """Fetch an attribute by code."""
    client = await get_client()
    return await client.get_attribute(code)


@mcp.tool()
async def list_categories(limit: int = 50, page: int = 1) -> dict[str, Any]:
    """List catalog categories."""
    client = await get_client()
    return await client.list_categories(limit=limit, page=page)


@mcp.tool()
async def get_category(code: str) -> dict[str, Any]:
    """Fetch a category by code."""
    client = await get_client()
    return await client.get_category(code)


@mcp.tool()
async def explain_product_search_json() -> dict[str, Any]:
    """Return a minimal reference for the raw Akeneo product search JSON accepted by search_products."""
    return {
        "preferred_collection_endpoint": "/products-uuid",
        "example": {
            "family": [{"operator": "IN", "value": ["default"]}],
            "enabled": [{"operator": "=", "value": True}],
            "categories": [{"operator": "IN", "value": ["ecommerce"]}],
        },
        "usage": "Pass the JSON object as a string via raw_search_json in search_products.",
        "note": "This is an escape hatch for advanced searches when the simple tool arguments are not enough.",
    }


@mcp.tool()
async def explain_reference_spec() -> dict[str, Any]:
    """Explain how the bundled Akeneo OpenAPI file should be used in this repo."""
    return {
        "file": "akeneo-openapi.yaml",
        "role": "Reference only",
        "why_not_codegen": [
            "Akeneo extends the OpenAPI document with vendor-specific x-* fields.",
            "The server is hand-written so auth, retries, and tool shape stay under project control.",
            "Spec examples and endpoint coverage are still useful when expanding the MCP surface.",
        ],
        "observed_extensions": [
            "x-validation-rules",
            "x-body-by-line",
            "x-app-token",
            "x-no-token",
            "x-warning",
            "x-immutable",
        ],
    }
