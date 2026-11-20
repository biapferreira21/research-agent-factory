"""Private, local configuration for model-provider adapters.

Credentials live below the data directory, which is excluded from source
control.  The web API only exposes connection state; it never serialises a
secret back to the browser.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import tempfile

from app.config import get_settings


PROVIDERS = {
    "openrouter": {
        "label": "OpenRouter",
        "environment": "OPENROUTER_API_KEY",
        "prefixes": ("sk-or-",),
    },
    "openai": {
        "label": "OpenAI",
        "environment": "OPENAI_API_KEY",
        "prefixes": ("sk-",),
    },
}


class IntegrationStore:
    """Load and persist local provider credentials without exposing them."""

    def __init__(self, data_root: Path):
        self.root = Path(data_root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "credentials.env"

    @staticmethod
    def _provider(provider: str) -> dict:
        key = str(provider).strip().casefold()
        if key not in PROVIDERS:
            raise ValueError("Unknown model provider")
        return PROVIDERS[key]

    def _read(self) -> dict[str, str]:
        if not self.path.is_file() or self.path.is_symlink():
            return {}
        values: dict[str, str] = {}
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if name in {item["environment"] for item in PROVIDERS.values()}:
                values[name] = value.strip()
        return values

    def _write(self, values: dict[str, str]) -> None:
        lines = ["# Local credentials. Never commit this file."]
        for provider in PROVIDERS.values():
            name = provider["environment"]
            if name in values:
                lines.append(f"{name}={values[name]}")
        payload = "\n".join(lines) + "\n"
        descriptor, temporary = tempfile.mkstemp(prefix="credentials-", suffix=".tmp", dir=self.root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def load(self) -> None:
        for name, value in self._read().items():
            os.environ[name] = value
        get_settings.cache_clear()

    def migrate_legacy_env(self, env_path: Path) -> int:
        """Move provider keys out of a repository-level .env file once."""
        env_path = Path(env_path).resolve()
        if not env_path.is_file() or env_path.is_symlink():
            return 0
        lines = env_path.read_text(encoding="utf-8").splitlines()
        names = {item["environment"] for item in PROVIDERS.values()}
        private = self._read()
        migrated = 0
        rewritten = []
        for line in lines:
            if "=" not in line or line.lstrip().startswith("#"):
                rewritten.append(line)
                continue
            name, value = line.split("=", 1)
            clean_name = name.strip()
            clean_value = value.strip().strip("'\"")
            if clean_name in names and clean_value:
                private.setdefault(clean_name, clean_value)
                os.environ[clean_name] = private[clean_name]
                rewritten.append(f"{clean_name}=")
                migrated += 1
            else:
                rewritten.append(line)
        if not migrated:
            return 0
        self._write(private)
        descriptor, temporary = tempfile.mkstemp(prefix="environment-", suffix=".tmp", dir=env_path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write("\n".join(rewritten) + "\n")
            os.replace(temporary, env_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        get_settings.cache_clear()
        return migrated

    def set_key(self, provider: str, api_key: str, *, persist: bool = True) -> dict:
        definition = self._provider(provider)
        value = str(api_key).strip()
        if len(value) < 20 or len(value) > 500 or re.search(r"\s", value):
            raise ValueError("Invalid API key")
        environment = definition["environment"]
        os.environ[environment] = value
        if persist:
            values = self._read()
            values[environment] = value
            self._write(values)
        get_settings.cache_clear()
        return self.status()[provider]

    def remove_key(self, provider: str) -> dict:
        definition = self._provider(provider)
        environment = definition["environment"]
        # An explicit empty value also prevents a repository-level .env from
        # silently reconnecting the provider during this process.
        os.environ[environment] = ""
        values = self._read()
        values[environment] = ""
        self._write(values)
        get_settings.cache_clear()
        return self.status()[provider]

    def status(self) -> dict[str, dict]:
        settings = get_settings()
        connected = {
            "openrouter": bool(settings.openrouter_api_key),
            "openai": bool(settings.openai_api_key),
        }
        return {
            name: {
                "id": name,
                "label": definition["label"],
                "configured": connected[name],
                "adapter": "built-in",
            }
            for name, definition in PROVIDERS.items()
        }

    def configured(self, provider: str) -> bool:
        self._provider(provider)
        return self.status()[provider]["configured"]
