from app.registry.mcp import CapabilityBlocked
from app.schemas.agent import AgentSpec
from app.schemas.capability import CapabilitySpec


def validate_capability_plan(agent: AgentSpec, plan: CapabilitySpec) -> None:
    if plan.agent_name != agent.name:
        raise CapabilityBlocked("CapabilitySpec pertence a outro agente.")
    if plan.memory != agent.memory or plan.runtime != agent.runtime:
        raise CapabilityBlocked("CapabilityPlanner não pode redesenhar memory/runtime.")
    capabilities = {item.name: item for item in plan.capabilities}
    if len(capabilities) != len(plan.capabilities):
        raise CapabilityBlocked("Capabilities duplicadas.")
    tools = {tool.name: tool for tool in agent.tools}
    if len(tools) != len(agent.tools):
        raise CapabilityBlocked("Tools duplicadas no AgentSpec.")
    for tool in agent.tools:
        capability = capabilities.get(tool.name)
        if tool.required and (capability is None or not capability.required):
            raise CapabilityBlocked(f"Capacidade obrigatória omitida: {tool.name}")
        if capability is not None and capability.source != tool.source:
            raise CapabilityBlocked(f"Origem da capacidade foi alterada: {tool.name}")
    for capability in plan.capabilities:
        if capability.source == "mcp" and capability.name not in tools:
            raise CapabilityBlocked(f"MCP não previsto no AgentSpec: {capability.name}")
