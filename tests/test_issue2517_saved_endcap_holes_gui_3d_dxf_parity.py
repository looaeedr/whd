"""#2517: saved Receiving Head/Tail holes share GUI and Engine 2D/3D/DXF.

One true .p6fold source carries two distinct physical CUTTING hole identities,
not a snapshot fixture pretending to be reloaded. PART_ONLY validation only.
"""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import export_verified_resolved_integration_bays
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from gui_modules.application import fold_designer_manufacturing_projection as gui
import phase6_project_file as project
from tests.test_issue2517_receiving_factory_saved_endcap_cutting_source import (
    SOURCE, REPO, _saved, _holes, _verified_request,
)

ROLES = ("head", "tail")


def _saved_project_with_distinct_endcap_holes(tmp_path):
    authored = _saved()
    features = _holes()
    authored["part_features"] = {
        role: list(features[role]) for role in ROLES
    }
    pristine = deepcopy(authored)
    target = project.write_project(
        tmp_path / "receiving-head-tail-with-real-holes.p6fold",
        {"schema": project.PROJECT_SCHEMA, "snapshot": authored},
    )
    reloaded = project.read_project(target)["snapshot"]
    assert target.is_file()
    assert authored == pristine
    for role in ROLES:
        assert reloaded["part_features"][role] == list(features[role])
    return authored, reloaded, features


def _specs(snapshot, source_features):
    return dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=snapshot, confirmed_endcap_features=source_features,
    ))


def test_reloaded_head_tail_distinct_holes_reach_gui_formed_mesh_and_verified_batch(
    tmp_path,
):
    authored, reloaded, features = _saved_project_with_distinct_endcap_holes(tmp_path)
    original_copy = deepcopy(authored)
    ctx = ManufacturingContext(resource_root=REPO, draw_stock=False)
    fresh = _specs(authored, features)
    loaded = _specs(reloaded, features)
    assert tuple(loaded) == ("box_body", "head", "tail")
    for role in ROLES:
        assert tuple(loaded[role].holes) == tuple(features[role])

    gui_dir = tmp_path / "gui-actual"
    gui_dir.mkdir()
    gui_renders = {}
    for role in ROLES:
        before = api.build_operator_part_render_data(fresh[role], ctx)
        final = api.build_operator_part_render_data(loaded[role], ctx)
        assert final.scene == before.scene
        assert final.fold_guides == before.fold_guides
        assert final.material.equals(before.material)
        assert final.material.is_valid and not final.material.is_empty
        assert final.metadata == before.metadata

        # The same persisted EndCap X/Y profiles fold the canonical 2D
        # material, rather than a view-only or independently guessed 3D.
        before_xy = authored["endcap_fold_profiles"][role]
        after_xy = reloaded["endcap_fold_profiles"][role]
        assert before_xy == after_xy
        before_mesh = api.project_independent_part_view_mesh(
            role, before,
            x_profile=before_xy["X"], y_profile=before_xy["Y"],
            thickness=SOURCE["t"],
        )
        after_mesh = api.project_independent_part_view_mesh(
            role, final,
            x_profile=after_xy["X"], y_profile=after_xy["Y"],
            thickness=SOURCE["t"],
        )
        assert before_mesh.triangles
        assert after_mesh.triangles == before_mesh.triangles
        assert after_mesh.fold_guides == before_mesh.fold_guides
        gui_renders[role] = final

        # Call the actual shipped GUI single-part export adapter. GUI must
        # serialize the cached Engine source instead of inventing holes.
        host = SimpleNamespace(
            _flush_phase6_authoritative_state=lambda: None,
            _require_verified_baseline_sources_for_manufacturing=lambda: None,
            _authoritative_render_data=lambda spec, context, expected=role: (
                final
                if spec is loaded[expected] and context is ctx else None
            ),
        )
        actual_gui = gui_dir / f"{role}.dxf"
        result = gui._export_authoritative_part(
            host, loaded[role], actual_gui, ctx,
        )
        assert Path(result) == actual_gui
        assert actual_gui.is_file()
        assert api.verify_saved_part_render_data_dxf(final, actual_gui).ok

    # Independent verified Engine batch must consume the same saved typed
    # PartSpecs and all real physical sheets, not the GUI's cached renders.
    verified = export_verified_resolved_integration_bays(
        (_verified_request(reloaded, features),),
        tmp_path / "engine-batch",
        context=ctx, pre_commit_guard=lambda: None,
    )
    assert verified.physical_dxf_roundtrip_verified
    assert not verified.complete_assembly_certified
    assert len(verified.output_files) == 5  # 3 Body sheets + 2 EndCaps
    values = tuple(Path(path) for path in verified.output_files.values())
    assert all(path.is_file() for path in values)
    for role in ROLES:
        (engine_path,) = tuple(
            path for path in values if path.name.endswith(role + ".dxf")
        )
        for path in (gui_dir / f"{role}.dxf", engine_path):
            opened = ezdxf.readfile(path)
            assert opened.audit().errors == []
            assert any(entity.dxf.layer == "CUTTING"
                       for entity in opened.modelspace())
            # Different saved physical hole radii must be present independently
            # in *each* serialized sink, not merely in the memory scene.
            diameter = features[role][0].diameter
            circles = tuple(
                entity for entity in opened.modelspace()
                if entity.dxftype() == "CIRCLE"
                and entity.dxf.layer == "CUTTING"
                and abs(float(entity.dxf.radius) * 2.0 - diameter) < 1e-6
            )
            assert circles, (role, path)
            assert api.verify_saved_part_render_data_dxf(
                gui_renders[role], path,
            ).ok
    assert authored == original_copy


def test_saved_head_hole_changed_after_reload_blocks_full_batch_without_partial_dxf(
    tmp_path,
):
    _authored, reloaded, original_features = (
        _saved_project_with_distinct_endcap_holes(tmp_path)
    )
    # The physical Project now records a different Head hole, while external
    # confirmed-source proof still names the original Head/Tail source.
    reloaded["part_features"]["head"] = [
        CircleFeature(
            18.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            Vec2(390.0, 150.0),
        )
    ]
    original = deepcopy(reloaded)
    output = tmp_path / "must-not-publish"
    with pytest.raises(ValueError, match="RECEIVING_SAVED_ENDCAP_SOURCE_FEATURES_MISMATCH"):
        export_verified_resolved_integration_bays(
            (_verified_request(reloaded, original_features),), output,
            context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert reloaded == original
    assert not output.exists()
