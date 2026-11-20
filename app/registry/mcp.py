"""Catálogo e política de seleção. Não inicia servidores nem executa ferramentas."""

from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from app.registry.models import RegistryRecord
from app.schemas.capability import CapabilitySpec


class CapabilityBlocked(RuntimeError):
    pass


RISK_LEVELS = {"low": 0, "medium": 1, "high": 2}
Risk = Literal["low", "medium", "high"]


class MCPTool(RegistryRecord):
    name: str = Field(min_length=1)
    capabilities: tuple[str, ...] = Field(min_length=1)
    permissions: tuple[str, ...] = ()
    required_domains: tuple[str, ...] = ()
    risk: Risk = "low"
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)


class RegisteredMCP(RegistryRecord):
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: Literal["draft", "approved", "disabled"] = "draft"
    authentication: Literal["none", "environment"] = "none"
    credential_env: str | None = Field(default=None, pattern=r"^[A-Z][A-Z0-9_]*$")
    tools: tuple[MCPTool, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_server(self):
        if (self.authentication == "environment") != (self.credential_env is not None):
            raise ValueError("Autenticação por environment exige apenas o nome da variável de credencial.")
        names = [tool.name for tool in self.tools]
        if len(names) != len(set(names)):
            raise ValueError("Ferramentas duplicadas no mesmo MCP.")
        return self


class MCPPolicy(RegistryRecord):
    # Política fornecida pelo harness, nunca inferida das permissões pedidas pelo LLM.
    allowed_permissions: tuple[str, ...] = ()
    allowed_domains: tuple[str, ...] = ()
    max_risk: Risk = "low"
    allow_paid: bool = False
    max_call_cost_usd: Decimal = Field(default=Decimal("0"), ge=0)


class MCPToolRef(RegistryRecord):
    server: str
    version: str
    tool: str


class MCPSelection(RegistryRecord):
    agent_name: str
    tools: tuple[MCPToolRef, ...] = ()
    omitted_optional: tuple[str, ...] = ()


class MCPConfiguration(RegistryRecord):
    reference: MCPToolRef
    allowed_permissions: tuple[str, ...]
    allowed_domains: tuple[str, ...]
    estimated_cost_usd: Decimal
    max_call_cost_usd: Decimal
    credential_env: str | None = None


class MCPRegistry(RegistryRecord):
    schema_version: Literal["1.0"] = "1.0"
    servers: tuple[RegisteredMCP, ...] = ()

    @model_validator(mode="after")
    def unique_versions(self):
        keys = [(server.name, server.version) for server in self.servers]
        if len(keys) != len(set(keys)):
            raise ValueError("Nome e versão de MCP duplicados.")
        return self

    @classmethod
    def load(cls, path: Path) -> "MCPRegistry":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def _allowed(self, server: RegisteredMCP, tool: MCPTool, policy: MCPPolicy) -> bool:
        cost = tool.estimated_cost_usd
        return (
            server.status == "approved"
            and RISK_LEVELS[tool.risk] <= RISK_LEVELS[policy.max_risk]
            and set(tool.permissions) <= set(policy.allowed_permissions)
            and set(tool.required_domains) <= set(policy.allowed_domains)
            and cost is not None
            and cost <= policy.max_call_cost_usd
            and (cost == 0 or policy.allow_paid)
        )

    def select(self, spec: CapabilitySpec, policy: MCPPolicy) -> MCPSelection:
        chosen: dict[tuple[str, str, str], MCPToolRef] = {}
        omitted = []
        for capability in spec.capabilities:
            if capability.source != "mcp":
                continue
            candidates = [
                (server, tool) for server in self.servers for tool in server.tools
                if capability.name in tool.capabilities and self._allowed(server, tool, policy)
            ]
            if not candidates:
                if capability.required:
                    raise CapabilityBlocked(f"Sem MCP aprovado e permitido para: {capability.name}")
                omitted.append(capability.name)
                continue
            # Desempate transparente para o MVP; JEV poderá escolher só deste conjunto.
            server, tool = min(candidates, key=lambda pair: (
                RISK_LEVELS[pair[1].risk], len(pair[1].permissions), len(pair[1].required_domains),
                pair[1].estimated_cost_usd, pair[0].name, pair[0].version, pair[1].name,
            ))
            key = (server.name, server.version, tool.name)
            chosen[key] = MCPToolRef(server=server.name, version=server.version, tool=tool.name)
        return MCPSelection(agent_name=spec.agent_name, tools=tuple(chosen.values()), omitted_optional=tuple(omitted))

    def configure(self, selection: MCPSelection, policy: MCPPolicy) -> tuple[MCPConfiguration, ...]:
        configurations = []
        seen = set()
        for reference in selection.tools:
            key = (reference.server, reference.version, reference.tool)
            if key in seen:
                raise CapabilityBlocked("Seleção contém uma ferramenta repetida.")
            seen.add(key)
            matches = [
                (server, tool) for server in self.servers for tool in server.tools
                if (server.name, server.version, tool.name) == key
            ]
            if not matches or not self._allowed(*matches[0], policy):
                raise CapabilityBlocked("Seleção contém ferramenta/versão não aprovada ou não permitida.")
            server, tool = matches[0]
            configurations.append(MCPConfiguration(
                reference=reference, allowed_permissions=tool.permissions,
                allowed_domains=tool.required_domains, estimated_cost_usd=tool.estimated_cost_usd,
                max_call_cost_usd=policy.max_call_cost_usd, credential_env=server.credential_env,
            ))
        return tuple(configurations)
