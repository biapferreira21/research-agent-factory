import hashlib
import json

import pytest

from app.planning.result_store import load_evaluation, save_evaluation
from research_demo import create_example_protocol
from results_demo import create_synthetic_results


def saved(tmp_path):
    protocol = create_example_protocol()
    return save_evaluation(tmp_path, protocol, create_synthetic_results(protocol))


def test_round_trip_and_new_directory_per_save(tmp_path):
    first, second = saved(tmp_path), saved(tmp_path)
    assert first != second
    loaded = load_evaluation(first)
    assert loaded["results"].origin == "synthetic"
    assert loaded["report"]["status"] == "not_evaluated"
    assert len(loaded["results"].measurements) == 6


@pytest.mark.parametrize("name", ["protocol.json", "results.json", "evaluation.json"])
def test_changed_file_rejected(tmp_path, name):
    directory = saved(tmp_path)
    (directory / name).write_text("{}")
    with pytest.raises(ValueError, match="Integridade"):
        load_evaluation(directory)


def test_missing_manifest_is_incomplete(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_evaluation(tmp_path)


def test_report_recomputed_even_if_checksum_updated(tmp_path):
    directory = saved(tmp_path)
    raw = b'{"criteria_met": true}'
    (directory / "evaluation.json").write_bytes(raw)
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["sha256"]["evaluation.json"] = hashlib.sha256(raw).hexdigest()
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="recalculada"):
        load_evaluation(directory)


def test_invalid_results_are_archived_without_approval(tmp_path):
    protocol = create_example_protocol()
    results = create_synthetic_results(protocol)
    results = results.model_copy(update={"measurements": results.measurements[:-1]})
    directory = save_evaluation(tmp_path, protocol, results)
    assert load_evaluation(directory)["report"]["status"] == "invalid_results"
