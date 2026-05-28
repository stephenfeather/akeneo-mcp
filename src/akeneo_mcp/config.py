from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_base_url(value: str) -> str:
    normalized = value.rstrip("/")
    for suffix in ("/api/rest/v1", "/api/rest", "/api"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
            break
    return normalized


@dataclass(frozen=True)
class Settings:
    akeneo_base_url: str
    akeneo_client_id: str
    akeneo_client_secret: str
    akeneo_username: str
    akeneo_password: str
    akeneo_verify_ssl: bool = True
    akeneo_timeout_seconds: float = 20.0
    akeneo_write_enabled: bool = False
    mcp_bind_host: str = "0.0.0.0"
    mcp_bind_port: int = 8094
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv()

        required = {
            "AKENEO_BASE_URL": os.getenv("AKENEO_BASE_URL"),
            "AKENEO_CLIENT_ID": os.getenv("AKENEO_CLIENT_ID"),
            "AKENEO_CLIENT_SECRET": os.getenv("AKENEO_CLIENT_SECRET"),
            "AKENEO_USERNAME": os.getenv("AKENEO_USERNAME"),
            "AKENEO_PASSWORD": os.getenv("AKENEO_PASSWORD"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                f"Missing required environment variables: {', '.join(sorted(missing))}"
            )

        return cls(
            akeneo_base_url=_normalize_base_url(required["AKENEO_BASE_URL"] or ""),
            akeneo_client_id=required["AKENEO_CLIENT_ID"] or "",
            akeneo_client_secret=required["AKENEO_CLIENT_SECRET"] or "",
            akeneo_username=required["AKENEO_USERNAME"] or "",
            akeneo_password=required["AKENEO_PASSWORD"] or "",
            akeneo_verify_ssl=_parse_bool(os.getenv("AKENEO_VERIFY_SSL"), True),
            akeneo_timeout_seconds=float(os.getenv("AKENEO_TIMEOUT_SECONDS", "20")),
            akeneo_write_enabled=_parse_bool(os.getenv("AKENEO_WRITE_ENABLED"), False),
            mcp_bind_host=os.getenv("MCP_BIND_HOST", "0.0.0.0"),
            mcp_bind_port=int(os.getenv("MCP_BIND_PORT", "8094")),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )
