import os
import tkinter as tk
from dataclasses import replace
from tkinter import filedialog

import ezdxf
import pytest

from ae_engine import WirePullBoxSpec, manufacturing_api as api
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import PROJECT_SCHEMA, read_project, write_project
from tests.test_issue3508_wire_pull_front_face_selection import _choose, _click_face, _fingerprints


@pytest.mark.requires_tk_display
@pytest.mark.skipif(not os.environ.get("DISPLAY"), reason="requires Tk display")
def test_front_and_rear_share_true_main_window_without_crossing_sources(tmp_path, monkeypatch):
    import gui

    spec = WirePullBoxSpec(843, 411, 223, 3)
    hole = CircleFeature(4, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(400, 260))
    mark = replace(hole, layer="MARKING", diameter=2, offset=Vec2(460, 280))
    manual = (("box_body", (hole, mark)),)
    proposal = api.propose_wire_pull_holes(spec, manual=manual)
    assert not proposal.conflicts
    snapshot = api.build_wire_pull_project_snapshot(spec, proposal)
    source = write_project(tmp_path / "before.p6fold", {"schema": PROJECT_SCHEMA, "snapshot": snapshot})
    witness = api.inspect_wire_pull_saved_export(source, expected_snapshot=snapshot)
    assert witness.manufacturing_blocker is None
    out = tmp_path / "old-dxf"
    dxf = api.save_wire_pull_saved_project_dxf(source, out, expected_source_sha256=witness.source_sha256)
    assert len(dxf) == 4
    for p in dxf.values():
        doc = ezdxf.readfile(p)
        assert doc.units == 4 and not doc.audit().errors
    original_fingerprints = _fingerprints(out)

    root = tk.Tk()
    def rear_edit(win, bounds):
        for key, value in zip(("left", "bottom", "right", "top"), bounds):
            win.rear_opening_fields[key].set(str(value))

    try:
        host = gui.Phase6PrimaryApplication(root)
        root.update()
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(source))
        host.fold_designer_app.project_file_menu.invoke(0)
        root.update()
        win = host.wire_pull_window
        assert win.window.winfo_viewable()
        assert win.controller.committed_snapshot() == snapshot
        win.view3d_button.invoke()
        root.update()
        front = win.physical.part("lid").mounting_faces[0]
        _choose(root, win, 1)
        assert win._mesh_selected_cover_face == ("lid", "outer")
        win._mesh_cancel_face_button.invoke()
        _click_face(root, win, front)
        assert win._mesh_face_selector.current() == 1
        win._mesh_confirm_face_button.invoke()
        assert win.controller.committed_snapshot() == snapshot

        win.rear_opening_enabled.set(True)
        rear_edit(win, (970, 150, 1030, 210))
        win.confirm()
        root.update()
        assert win._mesh_window is None and win._confirmed_cover_face is None
        assert api.wire_pull_rear_opening_bounds(win.proposal) == pytest.approx((970, 150, 1030, 210))

        win.fields["width"].set("637")
        replacement = (400, 150, 500, 210)
        rear_edit(win, replacement)
        assert win.preview(), win.status.get()
        assert not win.proposal.conflicts
        win.confirm()
        root.update()
        assert win.proposal.spec.width == 637
        assert api.wire_pull_rear_opening_bounds(win.proposal) == pytest.approx(replacement)
        assert dict(win.proposal.manual)["box_body"][:2] == (hole, mark)
        confirmed = win.controller.committed_snapshot()
        win.fields["width"].set("700")
        rear_edit(win, (415, 150, 515, 210))
        assert win.preview(), win.status.get()
        win.cancel()
        root.update()
        assert win.controller.committed_snapshot() == confirmed
        assert api.wire_pull_rear_opening_bounds(win.proposal) == pytest.approx(replacement)

        target = tmp_path / "after.p6fold"
        monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(target))
        win.save(save_as=True)
        assert win.status.get().startswith("已儲存專案")
        assert read_project(target)["snapshot"] == confirmed
        win.window.destroy()
        root.update()
        monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(target))
        host.fold_designer_app.project_file_menu.invoke(0)
        root.update()
        loaded = host.wire_pull_window
        assert loaded.window.winfo_viewable()
        assert loaded.controller.committed_snapshot() == confirmed
        assert api.wire_pull_rear_opening_bounds(loaded.proposal) == pytest.approx(replacement)
        assert dict(loaded.proposal.manual)["box_body"][:2] == (hole, mark)
        loaded.view3d_button.invoke()
        root.update()
        assert tuple(loaded._mesh_face_selector["values"]) == ("未選取", "前面（既有外蓋）")
        assert loaded._mesh_selected_cover_face is None
        _choose(root, loaded, 1)
        assert loaded._mesh_selected_cover_face == ("lid", "outer")
        assert loaded.controller.committed_snapshot() == confirmed

        monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(out))
        loaded.export_dxf()
        assert loaded.status.get() == "WIRE_PULL_REAR_COVER_JOINT_UNVERIFIED"
        assert _fingerprints(out) == original_fingerprints
        assert read_project(target)["snapshot"] == confirmed
    finally:
        root.destroy()
