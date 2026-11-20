# Python SDK

The package includes a small synchronous client for the same HTTP harness used
by the interface. Credentials are sent only to the local setup endpoint and are
never returned by the API.

```python
from app import AgentFactoryClient

with AgentFactoryClient("http://127.0.0.1:8765") as factory:
    factory.configure_provider("openrouter", "YOUR_KEY")
    project = factory.create_project(
        "Panel evidence",
        "How do fixed-effects and random-effects estimators differ under correlated unit effects?",
        "econometrics",
    )
    operation = factory.build_agent(
        project["id"],
        provider="openrouter",
        model="openrouter/free",
        budget_usd="1.00",
    )
    agent_build = factory.wait_job(operation["job_id"])
```

Connect an existing Obsidian vault and synchronise one project:

```python
factory.connect_obsidian(r"C:\Users\you\Documents\Research Vault")
factory.sync_obsidian(project["id"])
```

Main methods are `projects`, `project`, `create_project`, `factory_chat`,
`build_agent`, `agent_chat`, `wait_job`, `integrations`,
`configure_provider`, `connect_obsidian`, and `sync_obsidian`.

The client intentionally does not print, cache, or return API keys. A persisted
key is stored by the server in its ignored `data/credentials.env` file.
