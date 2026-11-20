import os
from decimal import Decimal
from uuid import uuid4

import pytest

from app.telemetry.build import BuildTelemetry
from app.telemetry.report import list_builds


def create(tmp_path, stamp):
    identifier = str(uuid4())
    directory = tmp_path / ".factory_runs" / identifier
    telemetry = BuildTelemetry(identifier, directory, Decimal(1), sink=None)
    telemetry.finish("passed")
    os.utime(directory, (stamp, stamp))
    return identifier, directory


def test_empty_root(tmp_path):
    assert list_builds(tmp_path) == {"builds": [], "total": 0, "next_offset": None}


def test_pagination_and_order(tmp_path):
    old, _ = create(tmp_path, 100)
    new, _ = create(tmp_path, 200)
    first = list_builds(tmp_path, limit=1)
    assert first["builds"][0]["build_id"] == new
    assert first["next_offset"] == 1
    second = list_builds(tmp_path, limit=1, offset=1)
    assert second["builds"][0]["build_id"] == old
    assert second["next_offset"] is None


def test_bad_log_does_not_hide_other_builds(tmp_path):
    _, directory = create(tmp_path, 100)
    (directory / "events.jsonl").write_bytes(b"\xff")
    create(tmp_path, 200)
    (tmp_path / ".factory_runs" / "not-a-build").mkdir()
    report = list_builds(tmp_path)
    assert report["total"] == 2
    assert {item["status"] for item in report["builds"]} == {"unreadable", "passed"}


def test_listing_does_not_load_scientific_archives(tmp_path, monkeypatch):
    create(tmp_path, 100)
    (tmp_path / ".research_evaluations").mkdir()
    import app.telemetry.report as reports
    monkeypatch.setattr(reports, "load_evaluation", lambda _: pytest.fail("Not needed for listing"))
    assert list_builds(tmp_path)["total"] == 1


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"limit": True}])
def test_invalid_pagination(tmp_path, kwargs):
    with pytest.raises(ValueError):
        list_builds(tmp_path, **kwargs)
