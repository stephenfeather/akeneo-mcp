# akeneo-mcp

Private-first MCP server for Akeneo PIM, designed to run close to a self-hosted Akeneo footprint.

This project provides a small, opinionated MCP surface over the Akeneo REST API with built-in token
management for Akeneo's OAuth password + refresh token flow. It is intended for deployments where the PIM is
reachable only over private networking such as Tailscale, a DigitalOcean private network, or an internal
Docker network.

The implementation already uses **FastMCP** as the server layer. The goal is not to generate a server from the
Akeneo spec, but to use the official MCP SDK ergonomics while keeping auth, retries, and tool design explicit.

## Why this exists

Generic OpenAPI-to-MCP gateways are useful when an API can be authenticated with a static header or query key.
Akeneo CE/EE REST authentication is different: it requires an OAuth token exchange and refresh cycle. This
project handles that natively and exposes a tighter, safer set of MCP tools for catalog exploration.

## Current scope

The initial release is deliberately read-only and exposes:

- `healthcheck_akeneo`
- `search_products` using Akeneo's preferred `/products-uuid` collection endpoint
- `get_product`
- `get_product_by_uuid`
- `list_families`
- `get_family`
- `list_attributes`
- `get_attribute`
- `list_categories`
- `get_category`
- `explain_product_search_json`
- `explain_reference_spec`

Write operations should be added only after explicit review and should stay behind a feature flag.

## Reference spec

This repo includes `akenea-openapi.yaml` as a **reference artifact**, not as the server's source of truth.
That file is useful for endpoint coverage, examples, and expansion planning, but Akeneo extends it with
vendor-specific fields such as `x-validation-rules`, `x-body-by-line`, `x-app-token`, `x-no-token`,
`x-warning`, and `x-immutable`.

That means:

- do not assume generic OpenAPI codegen or OpenAPI-to-MCP translation will behave correctly;
- use the file to guide endpoint additions and examples;
- keep the actual MCP contract hand-written and testable.

The same spec also explicitly recommends the UUID-based product endpoints, so this scaffold now defaults product
search to `/products-uuid` and adds direct UUID lookup.

## License

`akeneo-mcp` is licensed under **AGPL-3.0-only**.

That means:

- use is free of charge from this project maintainer's perspective;
- commercial usage is allowed;
- copyright and license notices must be preserved;
- if you modify the server and provide it to users over a network, you must make the modified source available
  under the same license.

If you want a different licensing model later, do that as a separate commercial exception or dual-license
decision. Keep the public project's terms unambiguous.

## Quick start

1. Copy the example environment file.
2. Fill in your Akeneo credentials.
3. Run the server locally or through Docker.

```bash
cp .env.example .env
python -m venv .venv
source .venv/bin/activate
pip install -e .
python -m akeneo_mcp
```

The server listens on `/mcp` over Streamable HTTP.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The included Compose file binds to `127.0.0.1:8094` by default so you don't accidentally publish the MCP
endpoint on every host interface.

## Environment

Required:

- `AKENEO_BASE_URL`
- `AKENEO_CLIENT_ID`
- `AKENEO_CLIENT_SECRET`
- `AKENEO_USERNAME`
- `AKENEO_PASSWORD`

Optional:

- `AKENEO_VERIFY_SSL=true`
- `AKENEO_TIMEOUT_SECONDS=20`
- `AKENEO_WRITE_ENABLED=false`
- `MCP_BIND_HOST=0.0.0.0`
- `MCP_BIND_PORT=8094`
- `LOG_LEVEL=INFO`

`AKENEO_BASE_URL` should be the root URL of the PIM, not the `/api/rest/v1` path.

Examples:

- `https://akeneo.example.internal`
- `http://akeneo-nginx`
- `http://10.0.0.25`

## Design notes

- The server manages Akeneo access tokens internally and retries once on `401` by forcing a token refresh.
- Tool responses are normalized for LLM consumption instead of returning raw API payloads everywhere.
- Product discovery prefers UUID-based Akeneo endpoints because the reference spec explicitly recommends them.
- The implementation is intentionally small and avoids vendor-specific dependencies outside the official MCP
  Python SDK and `httpx`.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
PYTHONPYCACHEPREFIX=/tmp/akeneo-mcp-pyc python -m py_compile src/akeneo_mcp/*.py
```

## Release posture

This repo is structured as a standalone OSS project suitable for publication. Before a public release, add:

- CI for syntax + smoke tests
- versioned changelog / release notes
- issue templates and security reporting guidance
