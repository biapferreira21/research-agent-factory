"""Configuração pública de um build. Credenciais pertencem apenas ao ambiente."""
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.retrieval.local import LocalIndex, Source
from app.retrieval.context import RetrievalConfig
from app.retrieval.evaluation import RetrievalCase


class PublicConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class KnowledgeConfig(PublicConfig):
    root: str
    sources: list[Source] = Field(min_length=1)
    domain: str | None = None
    project: str | None = None
    lines_per_chunk: int = Field(default=20, ge=1, le=200)
    limit: int = Field(default=5, ge=1, le=50)
    max_context_chars: int = Field(default=12000, ge=2, le=100000)
    cases: list[RetrievalCase] | None = Field(default=None, min_length=1)

    def create(self, base: Path) -> RetrievalConfig:
        return RetrievalConfig(LocalIndex(resolve(base, self.root), self.sources,
                                          lines_per_chunk=self.lines_per_chunk),
                               domain=self.domain, project=self.project, limit=self.limit,
                               max_context_chars=self.max_context_chars)


class AcceptanceConfig(PublicConfig):
    script: str
    timeout_seconds: float = Field(default=30, gt=0, le=120)


class RunConfig(PublicConfig):
    workspace_root: str = "generated_agents"
    budget_usd: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0.01"), le=Decimal("100.00"))
    max_repair_attempts: int = Field(default=0, ge=0, le=5, strict=True)
    decision_backend: Literal["configured", "jev"] = "configured"
    knowledge: KnowledgeConfig | None = None
    acceptance: AcceptanceConfig | None = None
    scientific_evaluations: bool = True


def resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def load_run_config(path: Path | None) -> tuple[RunConfig, Path]:
    if path is None:
        return RunConfig(), Path.cwd()
    path = path.resolve(strict=True)
    return RunConfig.model_validate_json(path.read_text(encoding="utf-8")), path.parent
