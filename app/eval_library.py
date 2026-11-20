"""Biblioteca mínima determinística de dimensões científicas; não certifica conclusões."""
from app.planning.research_validation import protocol_digest

DIMENSIONS = [
    {"id": "provenance", "description": "Vincular protocolo, código, dataset e fontes"},
    {"id": "hypothesis_vs_result", "description": "Distinguir hipótese, plano, dados sintéticos e medições executadas"},
    {"id": "multi_seed", "description": "Preservar as seeds previstas e não contar duplicados"},
    {"id": "matched_baseline", "description": "Comparar candidato e baselines nas mesmas métricas/seeds"},
    {"id": "executable_success", "description": "Comparar limiares pré-especificados, sem inferir significância"},
]


def plan(protocol):
    return {"version": 1, "protocol_sha256": protocol_digest(protocol), "selection": "mandatory_scientific_core",
            "dimensions": DIMENSIONS,
            "cases": [{"dimension": "multi_seed", "expected_seeds": protocol.seeds},
                      {"dimension": "matched_baseline", "expected_baselines": protocol.baselines,
                       "expected_metrics": [m.name for m in protocol.metrics]},
                      {"dimension": "provenance", "expected_protocol_sha256": protocol_digest(protocol)},
                      {"dimension": "hypothesis_vs_result", "require_explicit_origin": True},
                      {"dimension": "executable_success", "criteria": [c.model_dump(mode="json") for c in protocol.executable_criteria]}]}
