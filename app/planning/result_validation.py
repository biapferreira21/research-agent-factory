"""Verificações estruturais; não inferem sucesso científico a partir de texto."""
from app.planning.research_validation import protocol_digest
from app.schemas.research import ResearchProtocol
from app.schemas.results import ExperimentResults


def validate_results(protocol: ResearchProtocol, results: ExperimentResults) -> dict:
    protocol = ResearchProtocol.model_validate(protocol.model_dump())
    results = ExperimentResults.model_validate(results.model_dump())
    errors = []
    if results.protocol_sha256 != protocol_digest(protocol):
        errors.append("protocol_hash_mismatch")
    methods = [results.candidate_method, *protocol.baselines]
    if len({name.casefold() for name in methods}) != len(methods):
        errors.append("ambiguous_method_names")
    expected = {(method, metric.name, seed) for method in methods
                for metric in protocol.metrics for seed in protocol.seeds}
    actual = {(row.method, row.metric, row.seed) for row in results.measurements}
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing:
        errors.append("missing_measurements")
    if unexpected:
        errors.append("unexpected_measurements")
    return {"structurally_valid": not errors, "origin": results.origin,
            "scientific_success": "not_evaluated", "errors": errors,
            "missing": missing, "unexpected": unexpected,
            "expected_count": len(expected), "received_count": len(actual)}
