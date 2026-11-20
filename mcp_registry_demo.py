"""Catálogo fictício para estudar seleção. Não instala nem chama MCPs."""

from app.registry.mcp import MCPPolicy, MCPRegistry, MCPTool, RegisteredMCP
from app.schemas.capability import CapabilitySpec, RequiredCapabilitySpec


def example_registry() -> MCPRegistry:
    return MCPRegistry(servers=(RegisteredMCP(
        name="demo_papers", version="1.0", description="Servidor fictício, só para estudo",
        status="approved", tools=(
            MCPTool(name="search", capabilities=("literature_search",),
                    permissions=("network_read",), required_domains=("papers.example",), estimated_cost_usd="0"),
            MCPTool(name="delete", capabilities=("delete_records",),
                    permissions=("delete_data",), risk="high", estimated_cost_usd="0"),
        ),
    ),))


if __name__ == "__main__":
    registry = example_registry()
    requested = CapabilitySpec(agent_name="demo_agent", capabilities=[
        RequiredCapabilitySpec(name="literature_search", description="Pesquisar literatura", source="mcp"),
        RequiredCapabilitySpec(name="citation_analysis", description="Análise opcional", source="mcp", required=False),
    ])
    policy = MCPPolicy(allowed_permissions=("network_read",), allowed_domains=("papers.example",))
    selection = registry.select(requested, policy)
    print("Seleção no catálogo fictício:")
    print(selection.model_dump_json(indent=2))
    print("Configuração derivada pela Factory:")
    for configuration in registry.configure(selection, policy):
        print(configuration.model_dump_json(indent=2))
