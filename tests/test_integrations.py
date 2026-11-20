import json
import httpx
from fastapi.testclient import TestClient

from app.config import get_settings
from app.integrations import IntegrationStore
from app.obsidian import ObsidianBridge
from app.projects import ProjectStore
from app.sdk import AgentFactoryClient
from app.web import create_app
from app.wiki import ProjectWiki


def test_provider_credentials_are_private_and_persist_locally(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    get_settings.cache_clear()
    application = create_app(tmp_path / "data")
    secret = "sk-or-v1-test-credential-123456789"
    try:
        with TestClient(application) as client:
            session = client.get("/api/session").json()
            client.headers["x-factory-token"] = session["token"]
            response = client.put("/api/integrations/providers/openrouter", json={"api_key": secret})
            assert response.status_code == 200
            assert response.json()["provider"]["configured"] is True
            status = client.get("/api/integrations").json()
            assert secret not in json.dumps(status)
            assert secret not in json.dumps(client.get("/api/session").json())
        credential_file = tmp_path / "data" / "credentials.env"
        assert credential_file.is_file()
        assert secret in credential_file.read_text(encoding="utf-8")
    finally:
        get_settings.cache_clear()


def test_integration_store_reloads_provider_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    store = IntegrationStore(tmp_path)
    store.set_key("openai", "sk-test-openai-credential-123456789")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    store.load()
    assert store.status()["openai"]["configured"] is True
    assert store.remove_key("openai")["configured"] is False
    get_settings.cache_clear()


def test_legacy_env_migration_removes_secrets_from_project_config(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("OPENROUTER_API_KEY=sk-or-legacy-key-123456789\nBUILD_BUDGET_USD=1.00\n", encoding="utf-8")
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    get_settings.cache_clear()
    store = IntegrationStore(tmp_path / "data")
    assert store.migrate_legacy_env(env) == 1
    assert "OPENROUTER_API_KEY=\n" in env.read_text(encoding="utf-8")
    assert "BUILD_BUDGET_USD=1.00" in env.read_text(encoding="utf-8")
    assert "sk-or-legacy-key-123456789" in (tmp_path / "data" / "credentials.env").read_text(encoding="utf-8")
    get_settings.cache_clear()


def test_obsidian_sync_exports_and_imports_project_memory(tmp_path):
    data = tmp_path / "data"
    vault = tmp_path / "vault"
    vault.mkdir()
    store = ProjectStore(data)
    project = store.create("Causal model", "How should the treatment effect be identified?")
    wiki = ProjectWiki(store.directory(project["id"]))
    wiki.add("Assumption", "No unmeasured confounding")
    bridge = ObsidianBridge(data)
    assert bridge.connect(str(vault))["connected"] is True
    first = bridge.sync(project, store.directory(project["id"]))
    project_vault = next((vault / "Research Agent Factory").iterdir())
    assert first["exported"] == 1
    assert (project_vault / "Home.md").is_file()
    (project_vault / "Next experiment.md").write_text(
        "# Next experiment\n\nEstimate sensitivity bounds.", encoding="utf-8",
    )
    second = bridge.sync(project, store.directory(project["id"]))
    assert second["imported"] == 1
    assert any("sensitivity bounds" in item["content"] for item in wiki.entries())
    assert bridge.sync(project, store.directory(project["id"]))["imported"] == 0


def test_sdk_never_adds_a_key_to_read_requests():
    requests = []

    def handler(request):
        requests.append(request)
        if request.url.path == "/api/session":
            return httpx.Response(200, json={"token": "session-token"})
        if request.url.path == "/api/projects" and request.method == "POST":
            return httpx.Response(201, json={"id": "project-id"})
        return httpx.Response(200, json={"status": "ok"})

    with AgentFactoryClient("http://factory.test", transport=httpx.MockTransport(handler)) as factory:
        assert factory.create_project("A", "A sufficiently precise question?")["id"] == "project-id"
    assert requests[0].headers.get("x-factory-token") is None
    assert requests[1].headers["x-factory-token"] == "session-token"
