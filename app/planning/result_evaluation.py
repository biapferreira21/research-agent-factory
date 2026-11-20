"""Comparações determinísticas pré-especificadas; não testes de significância."""
from decimal import Decimal, localcontext

from app.planning.result_validation import validate_results
from app.schemas.research import ResearchProtocol
from app.schemas.results import ExperimentResults


def evaluate_results(protocol: ResearchProtocol, results: ExperimentResults) -> dict:
    protocol = ResearchProtocol.model_validate(protocol.model_dump())
    results = ExperimentResults.model_validate(results.model_dump())
    structural = validate_results(protocol, results)
    report = {"structure": structural, "origin": results.origin,
              "status": "not_evaluated", "criteria_met": None, "comparisons": []}
    if not structural["structurally_valid"]:
        report["status"] = "invalid_results"
        return report
    if not protocol.executable_criteria:
        return report
    directions = {metric.name: metric.direction for metric in protocol.metrics}
    for criterion in protocol.executable_criteria:
        def values(method):
            return [Decimal(str(row.value)) for row in results.measurements
                    if row.method == method and row.metric == criterion.metric]
        # Comparar somas equivale a comparar médias porque há as mesmas seeds.
        with localcontext() as context:
            context.prec = 1000
            candidate = sum(values(results.candidate_method), Decimal(0))
            baseline = sum(values(criterion.baseline), Decimal(0))
            count = Decimal(len(protocol.seeds))
            comparison = {"metric": criterion.metric, "baseline": criterion.baseline,
                          "direction": directions[criterion.metric],
                          "candidate_mean": str(candidate / count),
                          "baseline_mean": str(baseline / count),
                          "min_relative_improvement": str(criterion.min_relative_improvement)}
            if baseline <= 0:
                comparison.update(status="unsupported_baseline", passed=None)
            else:
                gain = baseline - candidate if directions[criterion.metric] == "minimize" else candidate - baseline
                comparison.update(status="evaluated", relative_improvement=str(gain / baseline),
                                  passed=gain >= baseline * criterion.min_relative_improvement)
            report["comparisons"].append(comparison)
    if any(item["passed"] is None for item in report["comparisons"]):
        report["status"] = "unsupported_baseline"
    else:
        report["criteria_met"] = all(item["passed"] for item in report["comparisons"])
        report["status"] = "synthetic_evaluation" if results.origin == "synthetic" else "evaluated"
    return report
