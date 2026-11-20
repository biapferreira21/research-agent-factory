import pytest
from pydantic import ValidationError

from app.planning.result_validation import validate_results
from app.schemas.results import ExperimentResults, Measurement
from research_demo import create_example_protocol
from results_demo import create_synthetic_results


def test_complete_synthetic_data_does_not_claim_success():
    protocol = create_example_protocol()
    report = validate_results(protocol, create_synthetic_results(protocol))
    assert report["structurally_valid"]
    assert report["origin"] == "synthetic"
    assert report["scientific_success"] == "not_evaluated"
    assert report["received_count"] == 6


def test_missing_and_unexpected_rows():
    protocol = create_example_protocol()
    results = create_synthetic_results(protocol)
    wrong = results.measurements[0].model_copy(update={"seed": 999})
    changed = results.model_copy(update={"measurements": (wrong, *results.measurements[1:])})
    report = validate_results(protocol, changed)
    assert report["errors"] == ["missing_measurements", "unexpected_measurements"]
    assert len(report["missing"]) == len(report["unexpected"]) == 1


def test_changed_protocol_detected():
    protocol = create_example_protocol()
    results = create_synthetic_results(protocol)
    protocol.stopping_rule = "another rule"
    assert "protocol_hash_mismatch" in validate_results(protocol, results)["errors"]


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "0.8"])
def test_invalid_values_rejected(value):
    with pytest.raises(ValidationError):
        Measurement(method="a", metric="error", seed=1, value=value)


def test_duplicate_rows_rejected():
    results = create_synthetic_results(create_example_protocol())
    data = results.model_dump()
    data["measurements"] += (data["measurements"][0],)
    with pytest.raises(ValidationError):
        ExperimentResults.model_validate(data)


def test_ambiguous_baseline_names_rejected():
    protocol = create_example_protocol()
    protocol.baselines.append(protocol.baselines[0])
    results = create_synthetic_results(protocol)
    assert "ambiguous_method_names" in validate_results(protocol, results)["errors"]
