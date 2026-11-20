"""Avaliação determinística das fontes efetivamente entregues no contexto."""
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.retrieval.context import RetrievalConfig
from app.retrieval.local import LocalIndex


class RetrievalCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    name: str = Field(min_length=1)
    query: str = Field(min_length=1)
    domain: str | None = None
    project: str | None = None
    expected_sources: tuple[str, ...]

    @model_validator(mode="after")
    def unique_sources(self):
        if any(not path.strip() for path in self.expected_sources):
            raise ValueError("Fonte esperada vazia.")
        if len(set(self.expected_sources)) != len(self.expected_sources):
            raise ValueError("Fontes esperadas repetidas.")
        return self


def evaluate(index: LocalIndex, cases: list[RetrievalCase], *, limit: int = 5,
             max_context_chars: int = 12000) -> dict:
    """Comparar conjuntos de fontes após filtro e limite de contexto.

    Um caso passa apenas se todas e só as fontes esperadas forem recuperadas.
    Casos negativos usam expected_sources=(). Não confundem recall com abstenção.
    """
    if not cases or len({case.name for case in cases}) != len(cases):
        raise ValueError("Fornecer casos com nomes únicos e uma suite não vazia.")
    known = {chunk.source.path for chunk in index.chunks}
    results = []
    for original in cases:
        case = RetrievalCase.model_validate(original.model_dump())
        expected = set(case.expected_sources)
        if not expected <= known:
            raise ValueError(f"Caso {case.name}: fonte esperada ausente do índice.")
        snapshot = RetrievalConfig(index, domain=case.domain, project=case.project,
                                   limit=limit, max_context_chars=max_context_chars).snapshot(case.query)
        retrieved = {hit["evidence"]["source"]["path"] for hit in snapshot["hits"]}
        correct = len(retrieved & expected)
        results.append({
            "case": case.model_dump(mode="json"),
            "passed": retrieved == expected,
            "precision": correct / len(retrieved) if retrieved else None,
            "recall": correct / len(expected) if expected else None,
            "missing_sources": sorted(expected - retrieved),
            "unexpected_sources": sorted(retrieved - expected),
            "snapshot": snapshot,
        })
    # Não fazer média de métricas indefinidas nem de casos negativos no recall.
    def mean(metric):
        values = [result[metric] for result in results if result[metric] is not None]
        return sum(values) / len(values) if values else None
    return {"evaluation_version": "source_sets_v1", "case_count": len(results),
            "passed_count": sum(result["passed"] for result in results),
            "pass_rate": sum(result["passed"] for result in results) / len(results),
            "mean_defined_precision": mean("precision"), "mean_defined_recall": mean("recall"),
            "results": results}
