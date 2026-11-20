"""Resultados inventados para estudar os contratos; não executa experiências."""
import json

from app.planning.research_validation import protocol_digest
from app.planning.result_validation import validate_results
from app.schemas.results import ExperimentResults, Measurement
from research_demo import create_example_protocol


def create_synthetic_results(protocol):
    return ExperimentResults(
        protocol_sha256=protocol_digest(protocol), origin="synthetic",
        candidate_method="Estratégia A", code_version="didactic-v1",
        dataset_version="synthetic-example-v1", parameters_json='{"iterations": 100}',
        measurements=tuple(Measurement(method=method, metric="mean_error", seed=seed, value=value)
                           for method, value in [("Estratégia A", 0.8), ("Estratégia B", 1.0)]
                           for seed in protocol.seeds),
    )


if __name__ == "__main__":
    protocol = create_example_protocol()
    results = create_synthetic_results(protocol)
    print(results.model_dump_json(indent=2))
    print(json.dumps(validate_results(protocol, results), indent=2))
