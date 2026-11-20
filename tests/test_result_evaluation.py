import pytest
from pydantic import ValidationError

from app.planning.result_evaluation import evaluate_results
from app.schemas.research import ResearchProtocol, SuccessCriterion
from research_demo import create_example_protocol
from results_demo import create_synthetic_results


@pytest.mark.parametrize("direction,candidate,baseline,expected", [
    ("minimize", 0.95, 1.0, True), ("minimize", 0.951, 1.0, False),
    ("maximize", 1.05, 1.0, True), ("maximize", 0.9, 1.0, False),
    ("minimize", 0.0, 0.0, None), ("maximize", -0.5, -1.0, None)])
def test_comparison_boundaries(direction, candidate, baseline, expected):
    protocol = create_example_protocol()
    protocol.metrics[0].direction = direction
    protocol.executable_criteria = [SuccessCriterion(metric="mean_error", baseline="Estratégia B",
                                                    min_relative_improvement="0.05")]
    results = create_synthetic_results(protocol)
    rows = tuple(row.model_copy(update={"value": candidate if row.method == results.candidate_method else baseline})
                 for row in results.measurements)
    report = evaluate_results(protocol, results.model_copy(update={"measurements": rows}))
    assert report["criteria_met"] is expected
    assert report["status"] == ("unsupported_baseline" if expected is None else "synthetic_evaluation")


def test_no_criteria_means_not_evaluated():
    protocol = create_example_protocol()
    assert evaluate_results(protocol, create_synthetic_results(protocol))["status"] == "not_evaluated"


def test_criteria_change_invalidates_existing_results():
    protocol = create_example_protocol()
    results = create_synthetic_results(protocol)
    protocol.executable_criteria = [SuccessCriterion(metric="mean_error", baseline="Estratégia B",
                                                    min_relative_improvement="0.05")]
    assert evaluate_results(protocol, results)["status"] == "invalid_results"


def test_unknown_criterion_rejected():
    protocol = create_example_protocol()
    data = protocol.model_dump()
    data["executable_criteria"] = [{"metric": "unknown", "baseline": "Estratégia B",
                                   "min_relative_improvement": "0.05"}]
    with pytest.raises(ValidationError):
        ResearchProtocol.model_validate(data)
