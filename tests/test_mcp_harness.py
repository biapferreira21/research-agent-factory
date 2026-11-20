import json
from pathlib import Path

import pytest

from app.builder.harness import BuilderHarness
from app.config import PROJECT_ROOT
from app.planning.fallbacks import fallback_capabilities
from app.registry.mcp import MCPPolicy, MCPRegistry
from app.schemas.agent import ToolSpec
from app.schemas.capability import RequiredCapabilitySpec
from app.tools.filesystem import create_filesystem_tools
from app.tools.testing import PytestResult
from harness_offline_demo import OfflineBuilder, offline_capability_planner, offline_planner
from mcp_registry_demo import example_registry


def mcp_agent(requirement):
    spec = offline_planner(requirement)
    spec.tools = [ToolSpec(name="literature_search", description="Search", source="mcp")]
    return spec


def make_harness(tmp_path, **changes):
    options = dict(root=tmp_path, planner=offline_planner, capability_planner=offline_capability_planner,
                   builder_factory=OfflineBuilder, test_runner=lambda _: PytestResult(0, "ok"),
                   event_sink=None, mcp_registry=MCPRegistry())
    options.update(changes)
    return BuilderHarness(**options)


def test_local_build_has_protected_capability_contracts(tmp_path):
    result = make_harness(tmp_path).build("demo")
    assert result.status == "passed"
    workspace = Path(result.workspace)
    assert json.loads((workspace / "mcp_selection.json").read_text())["tools"] == []
    assert json.loads((workspace / "mcp_configuration.json").read_text()) == []
    tools = {tool.name: tool for tool in create_filesystem_tools(workspace)}
    for name in ("capability_spec.json", "mcp_selection.json", "mcp_configuration.json"):
        with pytest.raises(ValueError, match="read-only"):
            tools["write_file"].invoke({"path": name, "content": "{}"})


def test_required_mcp_blocks_before_builder(tmp_path):
    result = make_harness(tmp_path, planner=mcp_agent,
                          builder_factory=lambda _: pytest.fail("Builder ran")).build("demo")
    assert result.status == "blocked"
    assert "literature_search" in result.errors[0]
    assert result.workspace == ""


@pytest.mark.parametrize("change", ["omit", "source", "agent", "runtime", "extra"])
def test_capability_planner_cannot_redesign_or_omit_required_tools(tmp_path, change):
    def planner(spec):
        plan = offline_capability_planner(spec)
        if change == "omit":
            plan.capabilities.clear()
        elif change == "source":
            plan.capabilities[0].source = "local"
        elif change == "agent":
            plan.agent_name = "other_agent"
        elif change == "runtime":
            # Criar cópia: o helper offline pode partilhar o objeto original.
            plan.runtime = plan.runtime.model_copy(update={"api": True})
        elif change == "extra":
            plan.capabilities.append(RequiredCapabilitySpec(name="invented", description="New", source="mcp"))
        return plan

    result = make_harness(tmp_path, planner=mcp_agent, capability_planner=planner).build("demo")
    assert result.status == "blocked"


def test_selected_mcp_is_saved_but_runtime_is_not_faked(tmp_path):
    result = make_harness(
        tmp_path, planner=mcp_agent, mcp_registry=example_registry(),
        mcp_policy=MCPPolicy(allowed_permissions=("network_read",), allowed_domains=("papers.example",)),
        builder_factory=lambda _: pytest.fail("MCP adapter is not installed"),
    ).build("demo")
    assert result.status == "blocked"
    assert "adaptador" in result.errors[0]
    selection = json.loads((Path(result.telemetry_path) / "mcp_selection.json").read_text())
    assert selection["tools"][0]["tool"] == "search"


def test_contract_tampering_fails_build(tmp_path):
    class TamperingBuilder(OfflineBuilder):
        def __init__(self, workspace):
            super().__init__(workspace)
            self.workspace = workspace

        def invoke(self, payload, *, config):
            super().invoke(payload, config=config)
            (self.workspace / "mcp_selection.json").write_text("{}", encoding="utf-8")

    result = make_harness(tmp_path, builder_factory=TamperingBuilder).build("demo")
    assert result.status == "failed"
    assert "mcp_selection.json" in result.errors[0]


def test_standard_research_tools_resolve_to_factory_mcps():
    spec = BuilderHarness._with_standard_research_tools(offline_planner("research"))
    assert {tool.name for tool in spec.tools} >= {"bm25_search", "citation_lookup", "literature_search"}
    selection = MCPRegistry.load(PROJECT_ROOT / "config" / "factory_mcp_registry.json").select(
        fallback_capabilities(spec),
        MCPPolicy(allowed_permissions=("project.documents.read", "network.public"),
                  allowed_domains=("api.crossref.org", "export.arxiv.org", "api.openalex.org",
                                   "api.semanticscholar.org")),
    )
    assert {f"{tool.server}/{tool.tool}" for tool in selection.tools} == {
        "factory-bm25/search", "factory-bm25/read_chunk", "factory-web/web_search",
    }
