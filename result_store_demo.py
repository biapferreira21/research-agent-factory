"""Guarda e relê uma avaliação sintética, sem executar experiências."""
from pathlib import Path

from app.planning.result_store import load_evaluation, save_evaluation
from app.schemas.research import SuccessCriterion
from research_demo import create_example_protocol
from results_demo import create_synthetic_results


if __name__ == "__main__":
    protocol = create_example_protocol()
    protocol.executable_criteria = [SuccessCriterion(metric="mean_error", baseline="Estratégia B",
                                                    min_relative_improvement="0.05")]
    results = create_synthetic_results(protocol)
    directory = save_evaluation(Path(__file__).resolve().parent / "generated_agents" / ".research_evaluations",
                                protocol, results)
    loaded = load_evaluation(directory)
    print("Origem:", loaded["results"].origin)
    print("Estado:", loaded["report"]["status"])
    print("Arquivo:", directory)
