"""Small synchronous SDK for the Research Agent Factory HTTP harness."""
from __future__ import annotations

import time
from typing import Any

import httpx


class AgentFactoryClient:
    """Typed-by-convention client for local or deployed factory instances."""

    def __init__(self, base_url: str = "http://127.0.0.1:8765", *, timeout: float = 180,
                 transport: httpx.BaseTransport | None = None):
        self._client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout,
                                    transport=transport, follow_redirects=False)
        self._token: str | None = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        self._client.close()

    def connect(self) -> dict[str, Any]:
        session = self._request("GET", "/api/session", authenticated=False)
        self._token = session["token"]
        return session

    def _request(self, method: str, path: str, *, authenticated: bool = True, **kwargs):
        if authenticated and not self._token:
            self.connect()
        headers = dict(kwargs.pop("headers", {}))
        if authenticated:
            headers["x-factory-token"] = self._token or ""
        response = self._client.request(method, path, headers=headers, **kwargs)
        response.raise_for_status()
        return response.json()

    def health(self) -> dict:
        return self._request("GET", "/api/health", authenticated=False)

    def integrations(self) -> dict:
        return self._request("GET", "/api/integrations", authenticated=False)

    def configure_provider(self, provider: str, api_key: str, *, persist: bool = True) -> dict:
        return self._request("PUT", f"/api/integrations/providers/{provider}",
                             json={"api_key": api_key, "persist": persist})

    def remove_provider(self, provider: str) -> dict:
        return self._request("DELETE", f"/api/integrations/providers/{provider}")

    def connect_obsidian(self, vault_path: str) -> dict:
        return self._request("PUT", "/api/integrations/obsidian", json={"path": vault_path})

    def projects(self) -> list[dict]:
        return self._request("GET", "/api/projects", authenticated=False)

    def project(self, project_id: str) -> dict:
        return self._request("GET", f"/api/projects/{project_id}", authenticated=False)

    def create_project(self, name: str, question: str, domain: str = "general") -> dict:
        return self._request("POST", "/api/projects",
                             json={"name": name, "question": question, "domain": domain})

    def factory_chat(self, project_id: str, query: str, *, provider: str | None = None,
                     model: str | None = None) -> dict:
        payload = {"query": query, "mode": "live", "model_provider": provider, "model": model}
        return self._request("POST", f"/api/projects/{project_id}/chat", json=payload)

    def build_agent(self, project_id: str, *, question: str | None = None,
                    provider: str | None = None, model: str | None = None,
                    budget_usd: str = "1.00") -> dict:
        payload = {"mode": "live", "backend": "configured", "repairs": 1,
                   "budget_usd": budget_usd, "question": question,
                   "model_provider": provider, "model": model}
        return self._request("POST", f"/api/projects/{project_id}/build", json=payload)

    def agent_chat(self, project_id: str, agent_job_id: str, query: str, *,
                   provider: str | None = None, model: str | None = None) -> dict:
        payload = {"query": query, "model_provider": provider, "model": model}
        return self._request("POST", f"/api/projects/{project_id}/agents/{agent_job_id}/chat", json=payload)

    def sync_obsidian(self, project_id: str) -> dict:
        return self._request("POST", f"/api/projects/{project_id}/obsidian/sync")

    def wait_job(self, job_id: str, *, interval: float = 0.5, timeout: float = 300) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            job = self._request("GET", f"/api/jobs/{job_id}", authenticated=False)
            if job["status"] not in {"queued", "running"}:
                return job
            time.sleep(interval)
        raise TimeoutError(f"Operation {job_id} did not finish within {timeout:g}s")
