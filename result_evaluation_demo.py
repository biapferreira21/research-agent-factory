"""Aplica um critério explícito a dados sintéticos, sem experiências reais."""
import json

from app.planning.result_evaluation import evaluate_results
from app.schemas.research import SuccessCriterion
from research_demo import create_example_protocol
from results_demo import create_synthetic_results


if __name__ == "__main__":
    protocol = create_example_protocol()
    protocol.executable_criteria = [SuccessCriterion(
        metric="mean_error", baseline="Estratégia B", min_relative_improvement="0.05")]
    # Construir resultados depois de fixar critérios: estes fazem parte do hash.
    results = create_synthetic_results(protocol)
    print(json.dumps(evaluate_results(protocol, results), ensure_ascii=False, indent=2))
