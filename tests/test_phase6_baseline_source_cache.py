from __future__ import annotations

from pathlib import Path

import pytest

from ae_engine import ae


def test_baseline_dxf_source_cache_reuses_same_fingerprint(tmp_path, monkeypatch):
    path = tmp_path / "part.dxf"
    path.write_text("dummy", encoding="utf-8")
    reads = []
    sentinel = object()
    monkeypatch.setattr(ae.ezdxf, "readfile", lambda p: (reads.append(str(p)) or sentinel))
    ae.clear_baseline_dxf_source_cache()

    first = ae.load_baseline_dxf_source(path)
    second = ae.load_baseline_dxf_source(path)

    assert first is sentinel
    assert second is sentinel
    assert reads == [str(path)]


def test_force_reload_bypasses_same_path_size_and_mtime_cache(tmp_path, monkeypatch):
    path = tmp_path / "part.dxf"
    path.write_text("dummy", encoding="utf-8")
    reads = []
    monkeypatch.setattr(ae.ezdxf, "readfile", lambda p: (reads.append(str(p)) or object()))
    ae.clear_baseline_dxf_source_cache()

    first = ae.load_baseline_dxf_source(path)
    ae.force_reload_baseline_dxf_sources()
    second = ae.load_baseline_dxf_source(path)

    assert first is not second
    assert reads == [str(path), str(path)]


def test_preview_can_use_last_known_good_when_network_stat_fails(tmp_path, monkeypatch):
    path = tmp_path / "part.dxf"
    path.write_text("dummy", encoding="utf-8")
    sentinel = object()
    monkeypatch.setattr(ae.ezdxf, "readfile", lambda _p: sentinel)
    ae.clear_baseline_dxf_source_cache()
    assert ae.load_baseline_dxf_source(path) is sentinel

    original_stat = Path.stat
    def broken_stat(self, *args, **kwargs):
        if self == path:
            raise OSError("network offline")
        return original_stat(self, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", broken_stat)

    assert ae.load_baseline_dxf_source(path, allow_unverified_source=True) is sentinel
    with pytest.raises(OSError, match="network offline"):
        ae.load_baseline_dxf_source(path, allow_unverified_source=False)


def test_status_api_marks_lkg_preview_as_source_unverified(tmp_path, monkeypatch):
    path = tmp_path / "part.dxf"
    path.write_text("dummy", encoding="utf-8")
    sentinel = object()
    monkeypatch.setattr(ae.ezdxf, "readfile", lambda _p: sentinel)
    ae.clear_baseline_dxf_source_cache()
    doc, status = ae.load_baseline_dxf_source_with_status(path)
    assert doc is sentinel
    assert status == ae.BASELINE_SOURCE_VERIFIED

    original_stat = Path.stat
    def broken_stat(self, *args, **kwargs):
        if self == path:
            raise OSError("network offline")
        return original_stat(self, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", broken_stat)

    doc, status = ae.load_baseline_dxf_source_with_status(path, allow_unverified_source=True)
    assert doc is sentinel
    assert status == ae.BASELINE_SOURCE_UNVERIFIED


def test_strict_status_api_rejects_unverified_source(tmp_path, monkeypatch):
    path = tmp_path / "part.dxf"
    path.write_text("dummy", encoding="utf-8")
    sentinel = object()
    monkeypatch.setattr(ae.ezdxf, "readfile", lambda _p: sentinel)
    ae.clear_baseline_dxf_source_cache()
    ae.load_baseline_dxf_source(path)

    original_stat = Path.stat
    def broken_stat(self, *args, **kwargs):
        if self == path:
            raise OSError("network offline")
        return original_stat(self, *args, **kwargs)
    monkeypatch.setattr(Path, "stat", broken_stat)
    with pytest.raises(OSError, match="network offline"):
        ae.load_baseline_dxf_source_with_status(path, allow_unverified_source=False)
