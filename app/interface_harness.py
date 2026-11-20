"""Machine-readable trace from the browser action to the Python research factory."""


def describe_interface_harness() -> dict:
    """Describe the production path used by the HTML harness.

    Keep this close to the HTTP layer so the interface can show the real Python
    entrypoints without duplicating the factory implementation in JavaScript.
    """
    return {
        "status": "connected",
        "interface_action": "POST /api/projects/{project_id}/build",
        "web_controller": "app.web.create_app.build",
        "runtime_entrypoint": "app.project_runtime.run_build",
        "factory_entrypoint": "app.builder.harness.BuilderHarness.build_research",
        "production_mode": "live",
        "stages": [
            {"id": "skills", "label": "Route approved research skills"},
            {"id": "retrieval", "label": "Snapshot project RAG and research memory"},
            {"id": "research_question", "label": "Formalize the research question"},
            {"id": "research_protocol", "label": "Create and validate the scientific protocol"},
            {"id": "scientific_architect", "label": "Design the research agent contract"},
            {"id": "capabilities", "label": "Approve MCP tools and runtime permissions"},
            {"id": "generation", "label": "Generate the Python agent and its tests"},
            {"id": "gates", "label": "Run contract, safety and structure gates"},
            {"id": "tests", "label": "Execute generated pytest validation"},
            {"id": "repair", "label": "Repair within the selected build budget"},
            {"id": "telemetry", "label": "Persist costs, events, contracts and code"},
        ],
        "runtime_services": [
            "ProjectStore / SQLite",
            "BM25 project retrieval",
            "SkillLibrary",
            "Model Registry and routing",
            "JEV decision service when selected",
            "factory-bm25 MCP",
            "factory-web MCP / arXiv, Crossref, OpenAlex and Semantic Scholar",
            "Research Wiki memory",
            "BuildTelemetry and CostTracker",
        ],
        "separate_entrypoints": [
            {
                "module": "app.cli and app.__main__",
                "purpose": "Start the web server and provide terminal administration commands.",
            },
            {
                "module": "app.mcp_server",
                "purpose": "Run as a bounded subprocess when an approved MCP tool is called.",
            },
            {
                "module": "app.run_config and app.telemetry.report",
                "purpose": "Terminal-only batch configuration and reporting.",
            },
        ],
        "scope": (
            "The HTML build action uses the complete scientific build pipeline. "
            "Terminal wrappers remain separate because they are operational entrypoints, not a second factory."
        ),
    }
