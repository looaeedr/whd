# -*- coding: utf-8 -*-
"""#2517 headless Engine owns CSV-V5 actual tier source and trial display trust."""
from dataclasses import replace
import inspect

import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_nfb_v5_operator_preview as owner
from gui_modules.application import receiving_nfb_v5_scene_preview as gui
from tests.test_issue1901_csv_v5_gui_real_tier_sources import _current_csv_tiers


class ReadOnlyCanvas:
    """Test the existing operator scene drawing with no Tk/GUI initialization."""
    def __init__(self):
        self.operations = []
    def delete(self, *args):
        self.operations.append(("delete", args))
    def create_line(self, *args, **kwargs):
        self.operations.append(("line", args, kwargs))
    def create_oval(self, *args, **kwargs):
        self.operations.append(("oval", args, kwargs))
    def create_text(self, *args, **kwargs):
        self.operations.append(("text", args, kwargs))


def test_real_two_tier_operator_preview_is_identical_headless_and_gui():
    snap, holes, door, root = _current_csv_tiers()
    real = api.preview_receiving_nfb_v5_real_base_sources(
        snap, "upper", door=door, configured_holes=holes, root_base_spec=root,
    )
    shown = gui.preview_v5_real_receiving_base_sources(
        snap, "upper", door=door, configured_holes=holes, root_base_spec=root,
    )
    assert real == shown
    assert [part.part_id for part in real] == [
        "base_plate:nfb_layer:0", "base_plate:nfb_layer:1",
    ]
    assert [part.hole_ids for part in real] == [
        ("nfb:csv:tier:0",), ("nfb:csv:tier:1",),
    ]
    assert all(not part.manufacturing_ready for part in real)
    assert api.require_receiving_nfb_v5_inner_door_trial_preview(door) is door.render_data
    assert all(api.require_receiving_nfb_v5_base_trial_preview(v) is v.render_data for v in real)
    canvas = ReadOnlyCanvas()
    assert gui.paint_v5_real_inner_door_trial(canvas, door) > 0
    assert gui.paint_v5_real_base_trial(canvas, real[0]) > 0
    assert any(x[0] == "line" for x in canvas.operations)


def test_headless_wrong_physical_root_or_stale_set_bay_rejected():
    snap, holes, door, root = _current_csv_tiers()
    with pytest.raises(ValueError, match="不同步"):
        api.preview_receiving_nfb_v5_real_base_sources(
            snap, "upper", door=door, configured_holes=holes,
            root_base_spec=replace(root, physical_id="base_plate:nfb_layer:0"),
        )
    snap["_receiving_runtime_selection"]["bay_id"] = "obsolete"
    with pytest.raises(ValueError, match="IDENTITY_DRIFT"):
        api.preview_receiving_nfb_v5_real_base_sources(
            snap, "upper", door=door, configured_holes=holes,
            root_base_spec=root,
        )


def test_unapproved_trials_cannot_spoof_manufacturing_status_to_gui():
    snap, holes, door, root = _current_csv_tiers()
    base = api.preview_receiving_nfb_v5_real_base_sources(
        snap, "upper", door=door, configured_holes=holes, root_base_spec=root,
    )[0]
    with pytest.raises(ValueError, match="尚未驗證"):
        api.require_receiving_nfb_v5_inner_door_trial_preview(
            replace(door, manufacturing_ready=True),
        )
    with pytest.raises(ValueError, match="未核准試作"):
        gui.paint_v5_real_base_trial(
            ReadOnlyCanvas(), replace(base, manufacturing_ready=True),
        )
    with pytest.raises(ValueError, match="未核准試作"):
        api.require_receiving_nfb_v5_base_trial_preview(
            replace(base, render_data=replace(
                base.render_data, metadata={
                    **base.render_data.metadata,
                    "nfb_base_mfg2_release_approved": True,
                },
            )),
        )


def test_gui_has_no_part_spec_material_or_physical_tier_decision():
    assert api.preview_receiving_nfb_v5_real_base_sources is owner.preview_receiving_nfb_v5_real_base_sources
    gui_source = inspect.getsource(gui)
    for forbidden in (
        "source_receiving_nfb_tier_base_specs",
        "receiving_base_plate_values(",
        "root_base_spec.physical_id",
        "root_base_spec.receiving_bend_pattern",
        "trial.manufacturing_ready",
        "nfb_base_mfg2_release_approved",
    ):
        assert forbidden not in gui_source
    assert "gui_modules" not in inspect.getsource(owner)
    assert "phase6_" not in inspect.getsource(owner)
