import pytest
from pydantic import ValidationError

from app.registry.mcp import (
    CapabilityBlocked, MCPPolicy, MCPRegistry, MCPSelection, MCPTool, MCPToolRef, RegisteredMCP,
)
from app.schemas.capability import CapabilitySpec, RequiredCapabilitySpec
from mcp_registry_demo import example_registry


def request(required=True, source="mcp"):
    return CapabilitySpec(agent_name="demo", capabilities=[RequiredCapabilitySpec(
        name="literature_search", description="Search", source=source, required=required,
    )])


def policy(**changes):
    return MCPPolicy(**dict({"allowed_permissions": ("network_read",), "allowed_domains": ("papers.example",)}, **changes))


def test_selects_only_needed_tool_not_whole_server():
    registry = example_registry()
    selection = registry.select(request(), policy())
    assert [ref.tool for ref in selection.tools] == ["search"]
    config, = registry.configure(selection, policy())
    assert config.allowed_permissions == ("network_read",)
    assert config.allowed_domains == ("papers.example",)
    assert "delete_data" not in config.allowed_permissions


@pytest.mark.parametrize("settings", [MCPPolicy(), policy(allowed_domains=()), policy(allowed_permissions=())])
def test_policy_is_not_inferred_from_requested_capabilities(settings):
    with pytest.raises(CapabilityBlocked):
        example_registry().select(request(), settings)


def test_unknown_required_blocks_and_optional_is_recorded():
    registry = MCPRegistry()
    with pytest.raises(CapabilityBlocked):
        registry.select(request(), policy())
    selection = registry.select(request(required=False), policy())
    assert selection.tools == ()
    assert selection.omitted_optional == ("literature_search",)


def test_local_capability_does_not_request_mcp():
    assert MCPRegistry().select(request(source="local"), MCPPolicy()).tools == ()


@pytest.mark.parametrize("status", ["draft", "disabled"])
def test_unapproved_server_is_filtered(status):
    data = example_registry().model_dump()
    data["servers"][0]["status"] = status
    with pytest.raises(CapabilityBlocked):
        MCPRegistry.model_validate(data).select(request(), policy())


@pytest.mark.parametrize("tool_changes", [
    {"risk": "high"}, {"estimated_cost_usd": None}, {"estimated_cost_usd": "0.1"},
    {"required_domains": ["other.example"]}, {"permissions": ["delete_data"]},
])
def test_risk_cost_and_scope_are_enforced(tool_changes):
    data = example_registry().model_dump()
    data["servers"][0]["tools"][0].update(tool_changes)
    with pytest.raises(CapabilityBlocked):
        MCPRegistry.model_validate(data).select(request(), policy())


def test_paid_tools_require_both_permission_and_cost_ceiling():
    data = example_registry().model_dump()
    data["servers"][0]["tools"][0]["estimated_cost_usd"] = "0.1"
    registry = MCPRegistry.model_validate(data)
    with pytest.raises(CapabilityBlocked):
        registry.select(request(), policy(allow_paid=True, max_call_cost_usd="0.09"))
    with pytest.raises(CapabilityBlocked):
        registry.select(request(), policy(max_call_cost_usd="1"))
    assert registry.select(request(), policy(allow_paid=True, max_call_cost_usd="0.1")).tools


@pytest.mark.parametrize("reference", [
    MCPToolRef(server="invented", version="1.0", tool="search"),
    MCPToolRef(server="demo_papers", version="99.0", tool="search"),
    MCPToolRef(server="demo_papers", version="1.0", tool="delete"),
])
def test_configuration_revalidates_untrusted_selection(reference):
    with pytest.raises(CapabilityBlocked):
        example_registry().configure(MCPSelection(agent_name="demo", tools=(reference,)), policy())


def test_same_tool_covering_two_capabilities_is_selected_once():
    data = example_registry().model_dump()
    data["servers"][0]["tools"][0]["capabilities"] = ("literature_search", "citations")
    registry = MCPRegistry.model_validate(data)
    spec = request()
    spec.capabilities.append(RequiredCapabilitySpec(name="citations", description="References", source="mcp"))
    assert len(registry.select(spec, policy()).tools) == 1


def test_duplicate_servers_and_tools_are_rejected():
    server = example_registry().servers[0]
    with pytest.raises(ValidationError):
        MCPRegistry(servers=(server, server))
    with pytest.raises(ValidationError):
        RegisteredMCP.model_validate(dict(server.model_dump(), tools=[server.tools[0], server.tools[0]]))


def test_authentication_contains_reference_not_secret():
    data = example_registry().servers[0].model_dump()
    data.update(authentication="environment", credential_env="PAPERS_API_KEY")
    registry = MCPRegistry(servers=(RegisteredMCP.model_validate(data),))
    configuration, = registry.configure(registry.select(request(), policy()), policy())
    assert configuration.credential_env == "PAPERS_API_KEY"
    with pytest.raises(ValidationError):
        RegisteredMCP.model_validate(dict(data, credential_env="sk-not-an-env-var"))


def test_registry_roundtrip(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(example_registry().model_dump_json(), encoding="utf-8")
    assert MCPRegistry.load(path) == example_registry()
