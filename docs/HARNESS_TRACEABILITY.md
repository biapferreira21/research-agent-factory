# HTML harness → Python factory

This document records which Python path each visible interface action executes.
The browser contains presentation and HTTP client code only; research decisions,
storage, budgets, builds, tools and validation remain in Python.

| Interface action | HTTP endpoint | Python execution path |
| --- | --- | --- |
| Create or open a project | `POST/GET /api/projects` | `app.web` → `ProjectStore` |
| Upload a research source | `POST /api/projects/{id}/documents` | `ProjectStore.add_document` → extraction/chunking → BM25 index → `ProjectWiki` |
| Search project RAG | `POST /api/projects/{id}/search` | `ProjectStore.search` → `app.retrieval.bm25.rank` |
| Discover papers | `POST /api/projects/{id}/web-search` | `app.research_web.search_papers` → arXiv/Crossref/OpenAlex/Semantic Scholar |
| Select research skills | `PUT/POST /api/projects/{id}/skills...` | `SkillLibrary` → optional `DecisionService/JevBackend` → telemetry |
| Chat with the factory | `POST /api/projects/{id}/chat` | `project_runtime.chat` → BM25/wiki/skills → Model Registry → cost telemetry |
| Create a research agent | `POST /api/projects/{id}/build` | `project_runtime.run_build` → `BuilderHarness.build_research` |
| Inspect an agent | `GET /api/projects/{id}/agents/{job}` | persisted contracts, code, RAG snapshot, skills, MCP configuration, costs and activity |
| Chat with an agent | `POST /api/projects/{id}/agents/{job}/chat` | `project_runtime.agent_chat` → validated contracts → BM25/MCP literature tools → model → telemetry |
| Evaluate measurements | `POST /api/projects/{id}/evaluations` | result schema validation → deterministic evaluation → integrity archive |
| Save/export memory | `/wiki` and `/wiki/export` | `ProjectWiki` → Markdown/Obsidian ZIP |

## Production agent-build path

The HTML form always submits `mode=live`. The server validates its model and
budget, creates a tracked background job, and calls:

```text
app.static.lab.js
  → app.web.create_app.build
    → app.project_runtime.run_build
      → app.builder.harness.BuilderHarness.build_research
```

`BuilderHarness` then routes skills, snapshots project evidence, formalizes the
research question, validates a protocol, creates the AgentSpec, approves MCP
capabilities, generates Python and tests, runs gates and pytest, attempts bounded
repairs, and persists contracts, events, costs and source code.

The interface reads the machine-readable description from `/api/harness`. The
collapsed **FULL PYTHON FACTORY CONNECTED** panel beside the build form displays
the same path and its eleven stages.

## Python entrypoints kept separate on purpose

- `app.cli` and `app.__main__` start the web server and expose terminal commands.
- `app.mcp_server` runs as a subprocess behind approved research tools.
- `app.run_config` and `app.telemetry.report` support terminal batch jobs and
  offline reporting.
- package `__init__.py` files define Python packages and contain no workflow.

These are operational entrypoints around the same implementation. Reimplementing
them in JavaScript would create a second factory and make behavior inconsistent.

The integration test
`test_html_harness_exposes_and_calls_the_live_python_factory` verifies that the
web request forwards `live` mode, the research brief, repair count and exact
budget to `project_runtime.run_build`. The remaining harness, research, MCP,
retrieval, cost and product tests verify the downstream Python pipeline.
