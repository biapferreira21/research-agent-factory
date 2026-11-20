from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ModelSpec(BaseModel):
    provider: Literal["openai", "openrouter"]
    model: str
    temperature: float = 0.0


class ToolSpec(BaseModel):
    name: str
    description: str
    required: bool = True
    source: Literal["local", "mcp"] = "local"


class MemorySpec(BaseModel):
    short_term: bool = True
    long_term: bool = False


class RuntimeSpec(BaseModel):
    cli: bool = True
    api: bool = False
    streaming: bool = False
    persistence: Literal["none", "memory", "sqlite", "postgres"] = "memory"


class EvaluationSpec(BaseModel):
    name: str
    description: str
    success_criteria: str
    type: Literal["code", "llm_judge", "human", "schema"] = "code"


class AgentSpec(BaseModel):
    spec_version: str = "1.0"
    research_protocol_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    name: str = Field(
        min_length=1,
        max_length=80,
        pattern=r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$",
        description="Nome snake_case, estavel e legivel"
    )

    @field_validator("name")
    @classmethod
    def reject_reserved_name(cls, value: str) -> str:
        reserved = {"con", "prn", "aux", "nul"}
        reserved.update(f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10))
        if value in reserved:
            raise ValueError("Nome reservado pelo Windows.")
        return value

    description: str
    objective: str

    inputs: list[str]
    outputs: list[str]

    architecture: Literal[
        "single_agent",
        "workflow",
        "langgraph",
    ]

    model: ModelSpec

    tools: list[ToolSpec] = Field(default_factory=list)
    memory: MemorySpec = Field(default_factory=MemorySpec)
    runtime: RuntimeSpec = Field(default_factory=RuntimeSpec)

    system_prompt: str

    evaluations: list[EvaluationSpec] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    
