# -*- coding: utf-8 -*-
"""#2517: Receiving multi-Bay partial DXF must run via public Engine API."""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

from ae_engine import manufacturing_api
from ae_engine import receiving_nfb_partial_batch_dispatcher as engine
from gui_modules.application import receiving_nfb_partial_batch_dispatcher as gui
from tests.test_issue1501_highlighted_partial_dxf_dispatcher import _ports


def test_public_engine_owns_full_batch_without_gui_reverse_dependency():
    assert manufacturing_api.export_highlighted_nfb_inner_doors is engine.export_highlighted_nfb_inner_doors
    assert manufacturing_api.require_highlighted_nfb_inner_doors is engine.require_highlighted_nfb_inner_doors
    assert gui.export_highlighted_nfb_inner_doors is manufacturing_api.export_highlighted_nfb_inner_doors
    assert gui.require_highlighted_nfb_inner_doors is manufacturing_api.require_highlighted_nfb_inner_doors
    engine_source = inspect.getsource(engine)
    gui_source = inspect.getsource(gui)
    assert "gui_modules" not in engine_source
    assert "phase6_" not in engine_source
    for forbidden in ("def _selection", "TemporaryDirectory(", "manifest.require_export(",
                      "os.link(", "NfbPartialExportManifest"):
        assert forbidden not in gui_source
    assert "from ae_engine.manufacturing_api import" in gui_source


def test_headless_engine_api_emits_real_files_for_exact_two_bays(tmp_path):
    ports, calls = _ports()
    results = manufacturing_api.export_highlighted_nfb_inner_doors(
        ports, set_index=0, bay_indices=(0, 1), output_directory=tmp_path,
    )
    assert len(results) == 2
    assert [manifest.scope.inner_door_part_id for _, manifest in results] == [
        "part-0", "part-1",
    ]
    assert all(Path(filename).read_bytes().endswith(b"EOF\n") for filename, _ in results)
    assert [index for _set, index, _path in calls] == [0, 1]
    assert not list(tmp_path.glob("*.json"))
    assert not list(tmp_path.glob(".whd-nfb-partial-stage-*"))


def test_headless_engine_api_rejects_stale_source_before_any_dxf(tmp_path):
    ports, calls = _ports(changed_source=True)
    with pytest.raises(ValueError, match="fresh submitted DXF proof"):
        manufacturing_api.export_highlighted_nfb_inner_doors(
            ports, set_index=0, bay_indices=(0, 1),
            output_directory=tmp_path,
        )
    assert calls == []
    assert list(tmp_path.iterdir()) == []


def test_headless_engine_api_held_report_never_claims_whole_box(tmp_path):
    import json
    ports, calls = _ports(changed_source=True)
    assert manufacturing_api.require_highlighted_nfb_inner_doors(
        ports, 0, (0, 1), allow_held=True
    ) == (0,)
    saved = manufacturing_api.export_highlighted_nfb_inner_doors(
        ports, set_index=0, bay_indices=(0, 1),
        output_directory=tmp_path, allow_held=True,
    )
    report = json.loads((tmp_path / "nfb_set1_partial_manifest.json").read_text())
    assert len(saved) == 1
    assert report["whole_cabinet_complete"] is False
    assert report["actual_export_count"] == 1
    assert report["exported"][0]["actually_emitted_part_ids"] == ["part-0"]
    assert report["not_exported_bays"][0]["bay_index"] == 1
    assert [index for _set, index, _path in calls] == [0]
