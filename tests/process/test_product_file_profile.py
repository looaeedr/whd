"""The per-file benchmark cannot change canonical selector ownership or hide missing jobs."""
from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime, timedelta, timezone

import pytest

from tools import product_file_profile as profile
from tools.product_ci_regression import PYTEST_PATHS


def test_file_inventory_preserves_exact_all_selectors_and_partial_node_scope():
    inventory = profile.file_inventory()
    assert len(inventory) > 1
    assert len({path for path, _ in inventory}) == len(inventory)
    assert Counter(s for _, selectors in inventory for s in selectors) == Counter(PYTEST_PATHS)
    assert all(path == s.split("::", 1)[0]
               for path, selectors in inventory for s in selectors)
    assert any("::" in s for _, selectors in inventory for s in selectors)


def test_two_matrices_cover_all_files_once_and_fit_256_limit():
    inventory = profile.file_inventory()
    a = profile.matrix_batch(0)
    b = profile.matrix_batch(1)
    assert a and b
    assert len(a) <= 256 and len(b) <= 256
    assert sorted(a + b) == list(range(len(inventory)))
    assert set(a).isdisjoint(b)
    with pytest.raises(ValueError, match="invalid batch"):
        profile.matrix_batch(2)


def test_profiling_rejects_out_of_range_file_index(tmp_path):
    with pytest.raises(ValueError, match="invalid file index"):
        profile.run_file(-1, tmp_path / "out.json")
    with pytest.raises(ValueError, match="invalid file index"):
        profile.run_file(len(profile.file_inventory()), tmp_path / "out.json")


def _sample_job(index, name, seconds=11, status="success"):
    base = datetime(2026, 10, 29, tzinfo=timezone.utc)
    fmt = lambda dt: dt.isoformat().replace("+00:00", "Z")
    return {
        "name": f"Profile {name} ({index})", "conclusion": status,
        "created_at": fmt(base), "started_at": fmt(base + timedelta(seconds=3)),
        "completed_at": fmt(base + timedelta(seconds=seconds + 3)),
        "html_url": f"https://github.com/example/actions/jobs/{index}",
        "steps": [{
            "name": "Run exact file selectors",
            "started_at": fmt(base + timedelta(seconds=3)),
            "completed_at": fmt(base + timedelta(seconds=3 + seconds - 1)),
        }],
    }


def test_summary_has_one_row_per_file_and_reports_exact_steps(tmp_path, monkeypatch):
    monkeypatch.setattr(profile, "file_inventory", lambda: (
        ("tests/a.py", ("tests/a.py::x",)),
        ("tests/b.py", ("tests/b.py",)),
    ))
    monkeypatch.setattr(profile, "PYTEST_PATHS", ("tests/a.py::x", "tests/b.py"))
    monkeypatch.setattr(profile, "_all_jobs", lambda *_: [
        _sample_job(0, "A", seconds=20), _sample_job(1, "B", seconds=8)
    ])
    assert profile.summarize("org/repo", 123, "token", tmp_path) == 0
    with (tmp_path / "per-file-timings.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert [r["file"] for r in rows] == ["tests/a.py", "tests/b.py"]
    assert [r["test_step_seconds"] for r in rows] == ["19.0", "7.0"]
    assert [r["runner_queue_seconds"] for r in rows] == ["3.0", "3.0"]
    assert "Observed peak overlapping runner jobs: 2" in (
        tmp_path / "summary.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("jobs", [
    [_sample_job(0, "A")],
    [_sample_job(0, "A"), _sample_job(1, "B", status="failure")],
])
def test_summary_fail_closed_for_missing_or_failed_file_job(tmp_path, monkeypatch, jobs):
    monkeypatch.setattr(profile, "file_inventory", lambda: (
        ("tests/a.py", ("tests/a.py",)),
        ("tests/b.py", ("tests/b.py",)),
    ))
    monkeypatch.setattr(profile, "PYTEST_PATHS", ("tests/a.py", "tests/b.py"))
    monkeypatch.setattr(profile, "_all_jobs", lambda *_: jobs)
    assert profile.summarize("org/repo", 123, "token", tmp_path) == 1
    assert (tmp_path / "per-file-timings.csv").is_file()


def test_summary_rejects_duplicate_job_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(profile, "file_inventory", lambda: (
        ("tests/a.py", ("tests/a.py",)),
    ))
    monkeypatch.setattr(profile, "_all_jobs", lambda *_: [
        _sample_job(0, "A"), _sample_job(0, "A")
    ])
    with pytest.raises(ValueError, match="duplicate profiling job"):
        profile.summarize("org/repo", 123, "token", tmp_path)
