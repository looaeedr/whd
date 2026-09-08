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
