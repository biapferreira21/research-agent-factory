import json
from uuid import uuid4

import pytest

from app.planning.build_evaluation import archive_build_results
from app.planning.research_validation import protocol_digest
from app.planning.result_store import load_evaluation
from research_demo import create_example_protocol
from research_harness_demo import offline_scientific_architect
from results_demo import create_synthetic_results


def fixture_build(tmp_path, status="passed"):
    identifier = str(uuid4())
    directory = tmp_path / ".factory_runs" / identifier
    directory.mkdir(parents=True)
    protocol = create_example_protocol()
    spec = offline_scientific_architect(protocol)
    spec.research_protocol_sha256 = protocol_digest(protocol)
    (directory / "research_protocol.json").write_text(protocol.model_dump_json(), encoding="utf-8")
    (directory / "agent_spec.json").write_text(spec.model_dump_json(), encoding="utf-8")
    (directory / "events.jsonl").write_text(json.dumps({"build_id": identifier, "stage": "finished", "status": status}))
    return identifier, directory, create_synthetic_results(protocol)


def test_links_results_and_preserves_build(tmp_path):
    identifier, directory, results = fixture_build(tmp_path)
    before = {path.name: path.read_bytes() for path in directory.iterdir()}
    archive = archive_build_results(tmp_path, identifier, results)
    loaded = load_evaluation(archive)
    assert str(loaded["results"].source_build_id) == identifier
    assert loaded["results"].origin == "synthetic"
    assert results.source_build_id is None
    assert before == {path.name: path.read_bytes() for path in directory.iterdir()}


@pytest.mark.parametrize("status", ["failed", "blocked", "started"])
def test_unfinished_or_failed_build_rejected(tmp_path, status):
    identifier, _, results = fixture_build(tmp_path, status)
    with pytest.raises(ValueError, match="concluído"):
        archive_build_results(tmp_path, identifier, results)
    assert not (tmp_path / ".research_evaluations").exists()


def test_wrong_protocol_or_build_rejected(tmp_path):
    identifier, _, results = fixture_build(tmp_path)
    for update in ({"protocol_sha256": "0" * 64}, {"source_build_id": uuid4()}):
        with pytest.raises(ValueError):
            archive_build_results(tmp_path, identifier, results.model_copy(update=update))


def test_invalid_path_id_rejected(tmp_path):
    _, _, results = fixture_build(tmp_path)
    with pytest.raises(ValueError):
        archive_build_results(tmp_path, "../escape", results)
