# Security

## Credentials

Use the **I/O** panel in the harness or environment variables. The harness
stores local provider keys in `data/credentials.env`; `data/`, `.env`, and
credential files are excluded from Git, source distributions, Docker build
contexts, and generated agents. API responses expose connection state only.

Before publishing a fork, run:

```powershell
git status --ignored
python -m pytest -q
python scripts/audit_release.py --wheel dist/research_agent_factory-0.1.0-py3-none-any.whl --bundle dist/research-agent-factory-kit-0.1.0.zip
```

If a credential was ever committed, removing the file is not sufficient.
Revoke the key at the provider and rewrite the repository history before making
the repository public.

## Deployment

The default server is a single-user local application. Put authentication and
HTTPS in front of it before exposing it to a network. Generated Python tests run
on the host, so public multi-user deployment also requires process or container
isolation.
