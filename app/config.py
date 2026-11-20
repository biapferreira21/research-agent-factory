
from functools import lru_cache
from pathlib import Path
from decimal import Decimal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_provider: str = "openrouter"

    openai_api_key: str | None = None
    openai_model: str = "gpt-5.5"

    openrouter_api_key: str | None = None
    openrouter_model: str = "openrouter/free"

    workspace_root: str = "generated_agents"
    model_registry_path: str = "config/model_registry.json"
    mcp_registry_path: str = "config/mcp_registry.json"
    allow_model_router: bool = True
    allowed_hosts: str = "127.0.0.1,localhost,testserver"
    build_budget_usd: Decimal = Field(default=Decimal("1.00"), ge=0, allow_inf_nan=False)
    model_call_reservation_usd: Decimal | None = Field(default=None, gt=0, allow_inf_nan=False)
    # Interactive replies should fail quickly enough to keep the harness usable.
    # Builds use a longer limit because they request structured research artifacts.
    model_chat_timeout_seconds: int = Field(default=60, ge=15, le=300)
    model_build_timeout_seconds: int = Field(default=150, ge=30, le=600)

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )
    max_repair_attempts: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_workspace_root() -> Path:
    configured = Path(
        get_settings().workspace_root
    ).expanduser()

    if configured.is_absolute():
        return configured.resolve()

    return (
        PROJECT_ROOT / configured
    ).resolve()


def get_model_registry_path() -> Path:
    configured = Path(get_settings().model_registry_path).expanduser()
    return configured.resolve() if configured.is_absolute() else (PROJECT_ROOT / configured).resolve()


def get_mcp_registry_path() -> Path:
    configured = Path(get_settings().mcp_registry_path).expanduser()
    return configured.resolve() if configured.is_absolute() else (PROJECT_ROOT / configured).resolve()


def get_allowed_hosts() -> list[str]:
    """Return the host names accepted by the web harness.

    A comma-separated environment value keeps local setup simple while allowing a
    deployed instance to name its public domain explicitly.
    """
    hosts = [host.strip() for host in get_settings().allowed_hosts.split(",") if host.strip()]
    return hosts or ["127.0.0.1", "localhost", "testserver"]
