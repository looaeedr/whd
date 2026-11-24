"""One owner ledger for selected real boards; this is not DXF admission."""
from pathlib import Path

import pytest

from ae_engine import manufacturing_api as api
from ae_engine.manufacturing_export import resolved_physical_render_parts
from ae_engine.sheetmetal_geometry import Vec2
from phase6_project_file import read_project
from tests.test_issue3414_scoped_marking_proto import _ids, _real_source

KEY = api.ROOT_MARKING_STORE_KEY
FIXTURE = Path(__file__).parent / "fixtures/issue1503_legacy_receiving_without_nfb_base.p6fold"


def test_strict_schema_and_scoped_read_through_without_migration():
    source = _real_source()
    owner = _ids(source)[0]
    scope = api.open_scoped_base_plate_editor(source, 0, 0)
    point = scope.context.render_data.material.representative_point()
    mark = api.create_physical_manual_marking(
        "base_plate", scope.context, (), midpoint=Vec2(point.x, point.y), length=8, angle_deg=37,
    )
    source[api.SCOPED_BASE_PLATE_MARKS] = api.commit_scoped_base_plate_marks(source, scope, [mark])
    assert api.read_workspace_marking_owner_record(source, owner)["features"] == [mark]
    assert KEY not in source
    assert api.read_workspace_marking_owner_record(source, "root-owner:" + "a"*32) is None
    for raw in ({"schema_version": True, "records": {}},
                {"schema_version": 2, "records": {}},
                {"schema_version": 1, "records": {owner: {}}}):
        with pytest.raises(ValueError, match="ROOT_MARKING_STORE"):
            api.normalize_workspace_root_marking_store(raw)


def test_native_same_store_two_boards_replay_edit_replace_and_legacy_clear(tmp_path, monkeypatch):
    import tkinter as tk
    from tkinter import filedialog, messagebox
    from gui import Phase6PrimaryApplication
    from gui_modules.project.export_actions import export_selected_dxf
    import ezdxf

    root = tk.Tk()
    try:
        host = Phase6PrimaryApplication(root)
        app = host.fold_designer_app
        menu = app.project_file_menu

        def open_path(path):
            monkeypatch.setattr(filedialog, "askopenfilename", lambda **kw: str(path))
            menu.invoke(0)
            root.update()
            assert host.project_controller.project_path == str(path)

        def save_as(stem):
            path = tmp_path / (stem + ".p6fold")
            monkeypatch.setattr(filedialog, "asksaveasfilename", lambda **kw: str(path))
            menu.invoke(2)
            root.update()
            assert path.is_file()
            return path, read_project(path)["snapshot"]

        def live():
            return {**app._phase6_input_snapshot, **app.designer_workspace.snapshot()}

        errors = []
        monkeypatch.setattr(messagebox, "showerror", lambda title, issue, **kw: errors.append((title, issue)))
        monkeypatch.setattr(messagebox, "showinfo", lambda *args, **kw: None)
        monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kw: True)

        def export_both(out):
            out.mkdir(exist_ok=True)
            for key in ("z", "head", "tail", "door", "base_plate", "ib", "ib_door"):
                getattr(host, f"export_{key}_var").set(key in ("head", "tail"))
            monkeypatch.setattr(filedialog, "askdirectory", lambda **kw: str(out))
            export_selected_dxf(host)

        def checked_ink(path, expected):
            doc = ezdxf.readfile(path)
            assert doc.header["$INSUNITS"] == 4
            assert len(doc.modelspace().query('*[layer=="CUTTING"]')) == 4
            assert len(doc.modelspace().query('*[layer=="BEND"]')) == 9
            ink = tuple(doc.modelspace().query('LWPOLYLINE[layer=="MARKING"]'))
            if expected is None:
                assert not ink
            else:
                assert len(ink) == 1
                assert tuple(map(tuple, ink[0].get_points("xy"))) == tuple((p.x, p.y) for p in expected.points)

        def read_receipt(key):
            app.activate_part(key)
            root.update()
            geometry = app._phase6_resolve_manufacturing_geometry()
            return api.open_physical_sheet_marking(key, snapshot=live(), geometry=geometry)

        def proposed(receipt, length):
            draft = api.open_workspace_owner_marking_draft(live(), receipt)
            geometry = app._phase6_resolve_manufacturing_geometry()
            render = dict(resolved_physical_render_parts(geometry))[receipt.part_key]
            where = render.material.representative_point()
            mark = receipt.create((), midpoint=Vec2(where.x, where.y), length=length, angle_deg=37)
            return api.prepare_workspace_owner_marking_commit(live(), draft, receipt, (mark,)), mark

        def apply(update, key):
            return app.designer_workspace.commit_owner_marking_update(
                update, model=app._phase6_input_snapshot["model"],
                read_current_receipt=lambda: read_receipt(key),
            )

        open_path(FIXTURE)
        for key in ("head", "tail"):
            assert app.remove_part(key)
            app.add_part(key)
            root.update()
        roots_path, _ = save_as("roots")
        open_path(roots_path)  # use stable re-opened signed authority, never pre-reopen nominal stock
        owners, marks = {}, {}
        for key, length in (("head", 8), ("tail", 13)):
            receipt = read_receipt(key)
            assert receipt.output_capability == "check_only"
            assert not api.open_workspace_owner_marking_draft(live(), receipt).saved_marks
            update, mark = proposed(receipt, length)
            imported = live()
            imported["part_features"] = {**imported.get("part_features", {}), key: (mark,)}
            # Even real same-sheet ink in the historical role stash is not
            # a durable owner's confirmed record.
            assert not api.open_workspace_owner_marking_draft(imported, receipt).saved_marks
            # Preparation/Cancel equals no persistence.
            assert api.read_workspace_marking_owner_record(live(), receipt.owner_id) is None
            assert apply(update, key)
            owners[key], marks[key] = receipt.owner_id, mark
            assert not any(api.is_manual_mark(f) for f in app.designer_workspace.features_for(key))
            if key == "head":
                app._phase6_publish_live_state(force=True)
                mixed = tmp_path / "one-owned-one-unmarked"
                export_both(mixed)
                assert not errors, errors
                checked_ink(mixed / "head.dxf", mark)
                checked_ink(mixed / "tail.dxf", None)
        app._phase6_publish_live_state(force=True)
        stored_path, stored = save_as("two-owners")
        assert set(stored[KEY]["records"]) == set(owners.values())
        assert KEY not in stored.get("workspace", {})
        open_path(stored_path)
        for key, owner in owners.items():
            receipt = read_receipt(key)
            assert receipt.owner_id == owner
            assert api.open_workspace_owner_marking_draft(live(), receipt).saved_marks == (marks[key],)

        both = tmp_path / "two-owned-verified-ordinary"
        export_both(both)
        assert not errors, errors
        checked_ink(both / "head.dxf", marks["head"])
        checked_ink(both / "tail.dxf", marks["tail"])
        old = {p.name: p.read_bytes() for p in both.iterdir()}
        assert len(old) == 2

        from ae_engine import manufacturing_verification
        real_verify = manufacturing_verification.verify_saved_part_render_data_dxf
        damaged = []
        def corrupt_after_readback(render, path):
            proof = real_verify(render, path)
            if proof.ok and not damaged:
                doc = ezdxf.readfile(path)
                ink = tuple(doc.modelspace().query('LWPOLYLINE[layer=="MARKING"]'))
                if ink:
                    doc.modelspace().delete_entity(ink[0])
                    doc.saveas(path)
                    damaged.append(str(path))
            return proof
        with monkeypatch.context() as scoped:
            scoped.setattr(manufacturing_verification, "verify_saved_part_render_data_dxf", corrupt_after_readback)
            export_both(both)
        assert damaged and "WHD_STAGED_DXF_VERIFIED_BYTES_CHANGED" in str(errors), errors
        assert {p.name: p.read_bytes() for p in both.iterdir()} == old
        errors.clear()

        # Same saved bytes and occupant IDs in a different physical project
        # path are not the same live ProjectController epoch.
        import os
        other_path = tmp_path / "another-actual-project-same-bytes.p6fold"
        other_path.write_bytes(stored_path.read_bytes())
        switch = []
        active_epoch = host.project_controller.project_load_epoch
        real_replace = os.replace
        def open_other_after_outer_move(src, dst, *args, **kwargs):
            result = real_replace(src, dst, *args, **kwargs)
            if (Path(dst).parent == both and Path(dst).suffix == ".dxf"
                    and ".whd-export-stage-" in str(src) and not switch):
                switch.append(Path(dst))
                host.load_phase6_project(other_path, open_designer=True)
                root.update()
            return result
        with monkeypatch.context() as scoped:
            scoped.setattr(os, "replace", open_other_after_outer_move)
            export_both(both)
        assert len(switch) == 1 and host.project_controller.project_load_epoch > active_epoch
        assert host.project_controller.project_path == str(other_path)
        assert "DXF 出圖專案已切換" in str(errors), errors
        assert {p.name: p.read_bytes() for p in both.iterdir()} == old
        errors.clear()
        open_path(stored_path)

        head = read_receipt("head")
        abandoned, _ = proposed(head, 9)
        change, updated = proposed(head, 10)
        assert apply(change, "head")
        with pytest.raises(ValueError, match="WORKSPACE_STALE"):
            apply(abandoned, "head")
        assert api.open_workspace_owner_marking_draft(live(), read_receipt("head")).saved_marks == (updated,)
        replacement_attempt, _ = proposed(read_receipt("head"), 11)
        assert app.remove_part("head")
        app.add_part("head")
        root.update()
        with pytest.raises(ValueError, match="OWNER_STALE"):
            apply(replacement_attempt, "head")
        app._phase6_publish_live_state(force=True)
        replaced, stored = save_as("replaced")
        assert owners["head"] in stored[KEY]["records"]   # old owner preserved/orphaned
        assert api.resolve_workspace_physical_root_owner(stored, "head") != owners["head"]
        open_path(replaced)
        assert not api.open_workspace_owner_marking_draft(live(), read_receipt("head")).saved_marks
        assert api.open_workspace_owner_marking_draft(live(), read_receipt("tail")).saved_marks == (marks["tail"],)

        # A real flat canonical physical row has no ordinary persisted owner;
        # neither this store nor the CHECK result invents one for that piece.
        geometry = app._phase6_resolve_manufacturing_geometry()
        from ae_engine.operator_physical_sheet_marking_preview import (
            open_selected_physical_marking_preview, project_selected_physical_marking_preview,
        )
        key = "box_body:box_body_back"
        r = dict(resolved_physical_render_parts(geometry))[key]
        flat = open_selected_physical_marking_preview(geometry, key)
        assert flat.material_class == "flat" and not flat.fold_guides
        point = r.material.representative_point()
        ink = project_selected_physical_marking_preview(
            flat, midpoint=Vec2(point.x, point.y), length=8, angle_deg=37,
        )
        assert len(ink) == 1 and ink[0].layer == "MARKING"
        with pytest.raises(ValueError, match="DURABLE_OWNER_REQUIRED"):
            api.open_physical_sheet_marking(key, snapshot=live(), geometry=geometry)

        open_path(FIXTURE)
        assert not live().get(KEY)
        _, separate = save_as("independent-legacy")
        assert KEY not in separate
    finally:
        root.destroy()
