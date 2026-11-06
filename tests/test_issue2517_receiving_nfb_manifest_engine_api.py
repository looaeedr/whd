# -*- coding: utf-8 -*-
"""#2517 read-only NFB manifest trust facts are owned by headless Engine."""
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_nfb_manifest_validation as engine
from ae_engine.receiving_nfb_export_manifest import derive_nfb_partial_export_manifest
from gui_modules.application import receiving_nfb_manifest_view as gui
from tests.test_issue1501_nfb_export_manifest import _prepared
from tests.test_issue1501_nfb_manifest_ui import _live_manifest_state


def test_headless_real_physical_receipt_matches_gui_disclosure(tmp_path):
    manifest = derive_nfb_partial_export_manifest(**_prepared(tmp_path))
    view = {**manifest.report(), "status": "PARTIAL_ONLY"}
    assert api.validate_receiving_nfb_manifest_view(view) is view
    assert view["actual_export_count"] == 6
    lines = gui.nfb_manifest_display_lines(view)
    assert "可加工 6 片" in lines[0]
    assert "MIDDLE_PLATE_NFB_COLOR150_UNVERIFIED" in "｜".join(lines)


def test_headless_forged_count_whole_ready_and_csv_source_fail_closed():
    view = _live_manifest_state()
    with pytest.raises(ValueError, match="displayed count"):
        api.validate_receiving_nfb_manifest_view({**view, "actual_export_count": 8})
    with pytest.raises(ValueError, match="full-ready display"):
        api.validate_receiving_nfb_manifest_view({**view, "status": "WHOLE_READY"})
    with pytest.raises(ValueError, match="cannot claim manufactured parts"):
        api.validate_receiving_nfb_manifest_view({
            "status": "CSV_SOURCE_RECHECK_ONLY", "actual_export_count": 1, "rows": (),
        })


def test_headless_highlight_selection_reads_live_scope_only_once():
    calls = []
    def get_view(si, bi):
        calls.append((si, bi))
        return _live_manifest_state(status="LEGACY") if bi else _live_manifest_state()
    rows = api.validate_receiving_nfb_highlighted_manifest(
        {"manifest": get_view}, 0, (0, 1),
    )
    assert calls == [(0, 0), (0, 1)]
    assert [row[1]["status"] for row in rows] == ["PARTIAL_ONLY", "LEGACY"]
    assert gui.highlighted_nfb_manifest_lines(
        {"manifest": get_view}, 0, (0, 1),
    )[-1].endswith("未配置 NFB｜原有加工流程")


def test_gui_is_only_text_renderer_no_physical_count_or_identity_guard():
    assert api.validate_receiving_nfb_manifest_view is engine.validate_receiving_nfb_manifest_view
    assert api.validate_receiving_nfb_highlighted_manifest is engine.validate_receiving_nfb_highlighted_manifest
    src = inspect.getsource(gui)
    assert "validate_receiving_nfb_manifest_view(" in src
    assert "validate_receiving_nfb_highlighted_manifest(" in src
    assert "actual_ready" not in src
    assert "manufacturing_ready" not in src
    assert "set(bays)" not in src
    assert "gui_modules" not in inspect.getsource(engine)
