from __future__ import annotations

import json


def test_active_divider_final_query_consumes_resolved_part(monkeypatch):
    from types import SimpleNamespace
    import fold_designer_bridge as bridge

    divider_key = "box_body:divider:main:HORIZONTAL:C0_R0|R1"
    canonical_render = object()

    class Resolved:
        def part(self, key):
            assert key == divider_key
            return SimpleNamespace(render_data=canonical_render)

    designer = SimpleNamespace(
        designer_workspace=SimpleNamespace(active_part=divider_key),
        _phase6_input_snapshot={},
    )
    monkeypatch.setattr(
        bridge, "_phase6_resolve_manufacturing_geometry", lambda _self: Resolved()
    )

    assert bridge._phase6_query_final_render_data(designer) is canonical_render


def test_project_file_strips_derived_final_geometry_on_write_and_read(tmp_path):
    import phase6_project_file as project

    payload = {
        "schema": project.PROJECT_SCHEMA,
        "snapshot": {
            "model": "受電箱",
            "w": 800.0,
            "h": 1600.0,
            "d": 350.0,
            "t": 2.0,
            "fw": 31.0,
        },
        "final_geometry": {
            "box_body:divider:main:HORIZONTAL:C0_R0|R1": {
                "material": "DERIVED_RENDER_CACHE_MUST_NOT_PERSIST",
                "placement": {"z": 174.0},
                "relief": {"probe": [47.0, 26.0]},
            }
        },
    }

    path = project.write_project(tmp_path / "dm4-project", payload)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw.get("final_geometry") == {}
    assert "DERIVED_RENDER_CACHE_MUST_NOT_PERSIST" not in path.read_text(encoding="utf-8")

    loaded = project.read_project(path)
    assert loaded.get("final_geometry") == {}


def test_corner_data_non_active_divider_uses_resolved_final_geometry(monkeypatch):
    """Corner Data selection must not fall back to raw Divider geometry."""
    from types import SimpleNamespace
    import fold_designer_bridge as bridge

    divider_key = "box_body:divider:receiving-main:HORIZONTAL:C0_R0|R1"
    canonical_render = object()
    raw_render = object()

    class Resolved:
        def part(self, key):
            assert key == divider_key
            return SimpleNamespace(render_data=canonical_render)

    designer = SimpleNamespace(
        designer_workspace=SimpleNamespace(active_part="box_body"),
        _phase6_input_snapshot={},
        _scene_query_callback=lambda *_args, **_kwargs: raw_render,
    )
    monkeypatch.setattr(
        bridge, "_phase6_resolve_manufacturing_geometry", lambda _self: Resolved()
    )

    assert bridge._phase6_render_data_for_blank(designer, divider_key) is canonical_render


def test_receiving_divider_resolved_cross_survives_dxf_export_reopen(tmp_path):
    import fold_designer_bridge as bridge
    from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
    from ae_engine.manufacturing_api import (
        save_resolved_manufacturing_geometry_dxf,
        verify_saved_resolved_manufacturing_geometry_dxf,
    )
    from tests.test_issue39_divider_relief import _snapshot, _body_part, _divider_part

    snapshot = _snapshot()
    body = _body_part(snapshot)
    divider, divider_part = _divider_part(snapshot)
    solved_parts, diagnostics, _family_joints = bridge._phase6_resolve_family_divider_reliefs(
        (body, divider_part),
        finished_dimensions=(snapshot["w"], snapshot["h"], snapshot["d"]),
        sheet_thickness=snapshot["t"],
        clearance=0.0,
    )
    solved = next(part for part in solved_parts if part.part_key == divider.stable_id)
    relief = dict(solved.render_data.metadata["divider_assembly_relief"])
    assert relief["verified"] is True
    assert relief["corner_type"] == "CROSS"

    resolved = ResolvedManufacturingGeometry(parts=(
        ResolvedManufacturingPart(
            part_key=solved.part_key,
            render_data=solved.render_data,
            x_profile=tuple(solved.x_profile),
            y_profile=tuple(solved.y_profile),
            placement=solved.placement,
            offset=tuple(solved.offset),
        ),
    ))
    outputs = save_resolved_manufacturing_geometry_dxf(
        resolved, tmp_path, overwrite=True
    )
    assert divider.stable_id in outputs
    acceptance = verify_saved_resolved_manufacturing_geometry_dxf(
        resolved, tmp_path
    )
    assert acceptance.ok, acceptance.issues
    assert diagnostics and diagnostics[0].candidate_status == "CERTIFIED_REGISTRY_VERIFIED"
