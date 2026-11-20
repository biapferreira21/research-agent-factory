# Complete research-agent MVP

The factory now treats a research agent as a prepared research workspace, not only generated Python.

## Build sequence

1. `app.research_intake.assess_research_brief` checks that the brief names a topic and a researchable relationship, effect, comparison, or outcome.
2. The Factory terminal stays in `INTAKE` while the question is incomplete. The model receives the missing dimensions and asks one clarification question at a time.
3. `app.project_runtime.run_build` blocks direct API calls that try to bypass intake.
4. `SkillLibrary.select` proposes up to eight relevant skills and merges them with any skills the user selected manually.
5. The local `factory-web` MCP searches arXiv, Crossref, OpenAlex, and Semantic Scholar.
6. `app.research_seed.seed_research_memory` writes a cited Markdown starter pack into project RAG and caches up to two available arXiv PDFs.
7. The starter pack includes a Google Scholar verification link. Google Scholar is not scraped because it has no supported public API.
8. The Python `BuilderHarness` formalizes `ResearchQuestionSpec`. Any remaining `open_questions` block generation and send the project back to intake.
9. The harness creates and protects the research question, protocol, capability, MCP, runtime, evaluation, and agent contracts.
10. Generated code must pass gates and tests before the agent is marked `READY`.
11. `research_library.json`, the RAG snapshot, selected skills, MCPs, generated Python, cost record, and protocol remain attached to the individual agent.

## Persisted research base

Each successful live build can contain:

- `research_library.json`: search query, provider records, citations, errors, PDFs, and the Google Scholar verification URL.
- `research-starter-<hash>.md`: readable literature candidate set indexed by project BM25.
- `arxiv-<id>.pdf`: open arXiv PDFs that could be downloaded and parsed.
- `research_question.json`: the final structured question.
- `research_protocol.json`: the validated protocol.
- `skills_selection.json`: the methodological skills available to the agent.
- `mcp_selection.json` and `runtime_config.json`: the exact bounded tools available at runtime.

Metadata search produces candidates, not verified conclusions. The generated agent must screen methodological fit and cite the stored source identifiers before treating a paper as evidence.
