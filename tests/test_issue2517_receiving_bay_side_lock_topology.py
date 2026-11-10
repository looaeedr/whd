"""Receiving Set/Bay actual side-lock CUTTING must follow adjacent Joint topology.

The dedicated side-panel DXFs have six Ø10.5 source lock holes on each side.
The factory Joint resolver supplies the separate certified Ø16 mating holes.
Test actual physical PartSpecs, real three-sheet FinalScene and disk DXF reopen,
not a debug drawing, grouped filename or mock-only expectation.
"""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from ae_engine.receiving_layout import (
    new_receiving_layout,
    project_receiving_bay_legacy_aliases,
    resize_receiving_bays,
    resize_receiving_sets,
)

ROOT = Path(__file__).resolve().parents[1]


def _source(layout):
    data = family_policy.apply_fresh_family_defaults({}, "受電箱")
    data.update({"model": "受電箱", "active_mode": "set_bay",
                 "w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0,
                 "receiving_layout": layout})
    data["box_body_structure_state"] = api.resolve_receiving_box_body_structure_state(None)
    data["box_body_fold_profile"] = api.build_box_body_fold_profile(data)
    data["endcap_fold_profiles"] = {
        role: api.build_endcap_xy_fold_profiles(data, part_key=role)
        for role in ("head", "tail")
    }
    data["endcap_corner_policies"] = {
        role: family_policy.endcap_corner_policy(
            "受電箱", frame_width=data["fw"], thickness=data["t"],
            state=data["box_body_structure_state"],
        ) for role in ("head", "tail")
    }
    return data


def _body_for(source, set_index, bay_index):
    selected = project_receiving_bay_legacy_aliases(
        source, set_index=set_index, bay_index=bay_index,
    )
    body = api.build_box_body_operator_part_spec(
        selected, model_name="受電箱",
        fold_profile=selected["box_body_fold_profile"],
        structure_state=selected["box_body_structure_state"],
        endcap_y_profiles={
            role: selected["endcap_fold_profiles"][role]["Y"]
            for role in ("head", "tail")
        },
        snapshot=selected,
    )
    return body, api.build_box_body_structure_render_data(
        body, ManufacturingContext(resource_root=ROOT),
    )


def _cutting_radius_count(entities, radius):
    return sum(
        e.dxftype() == "CIRCLE" and e.dxf.layer == "CUTTING"
        and abs(float(e.dxf.radius) - radius) < 1e-6
        for e in entities
    )


def _lock_face_features(body, face):
    return tuple(
        feature for feature in body.face_features.get(face, ())
        if getattr(feature, "source_type", None) == "receiving_joint_side_lock"
    )


def _layout(bay_count):
    layout = new_receiving_layout(width=800, height=1600, depth=350)
    return resize_receiving_bays(layout, set_index=0, bay_count=bay_count)


@pytest.mark.parametrize("bay_count,expected", (
    (1, ((False, False),)),
    (2, ((False, True), (True, False))),
    (3, ((False, True), (True, True), (True, False))),
))
def test_real_bay_side_cutting_and_independent_baseline_layers_reopen(
    tmp_path, bay_count, expected,
):
    source = _source(_layout(bay_count))
    original = deepcopy(source)
    for bay_index, expected_sides in enumerate(expected):
        body, render = _body_for(source, 0, bay_index)
        assert body.receiving_side_lock_participation == expected_sides
        assert {p.role for p in render.pieces} == {
            "left_side", "back", "right_side"
        }
        for face, role, joined in (
            ("left", "left_side", expected_sides[0]),
            ("right", "right_side", expected_sides[1]),
        ):
            piece = next(p for p in render.pieces if p.role == role)
            assert piece.render_data.metadata["baseline_side_lock_participation"] is joined
            assert piece.render_data.metadata["baseline_side_lock_certified_count"] == 6
            assert piece.render_data.metadata["baseline_feature_count"] == (9 if joined else 3)
            assert len(_lock_face_features(body, face)) == (2 if joined else 0)
            target_dir = tmp_path / f"bay_{bay_index+1}" / role
            identifier = f"bay{bay_index+1}_{role}"
            outputs = api.save_verified_final_scene_batch_dxf(
                ((identifier, piece.render_data),), target_dir,
                pre_commit_guard=lambda: None,
            )
            path = Path(outputs[identifier])
            opened = ezdxf.readfile(path)
            assert not opened.audit().errors
            assert api.verify_saved_part_render_data_dxf(piece.render_data, path).ok
            msp = opened.modelspace()
            # Six source Ø10.5 CUTTING holes only on actual adjacent sides.
            assert _cutting_radius_count(msp, 5.25) == (6 if joined else 0)
            # Certified Joint Ø16 CUTTING holes likewise only at mating sides.
            assert _cutting_radius_count(msp, 8.0) == (2 if joined else 0)
            # Original independent side features remain on both free edges:
            # left Ø5.1 CUTTING, right Ø13.1 MARKING, plus BLIND_HOLE.
            assert sum(e.dxftype() == "CIRCLE" and e.dxf.layer == "BLIND_HOLE"
                       for e in msp) == 1
            if face == "left":
                assert _cutting_radius_count(msp, 2.55) == 2
            else:
                assert sum(e.dxftype() == "CIRCLE" and e.dxf.layer == "MARKING"
                           and abs(float(e.dxf.radius) - 6.55) < 1e-6
                           for e in msp) == 2
    assert source == original


def test_fresh_family_nondefault_dimensions_never_borrow_nominal_bay_side_locks():
    dimensions = {"w": 920.0, "h": 1770.0, "d": 410.0, "t": 2.5}
    body = dict(api.build_receiving_factory_confirmed_parts(
        dimensions, confirmation="fresh_family_confirmed",
    ))["box_body"]
    assert (body.width, body.height, body.depth, body.thickness) == (
        920.0, 1770.0, 410.0, 2.5,
    )
    assert body.receiving_side_lock_participation is None
    assert not _lock_face_features(body, "left")
    assert not _lock_face_features(body, "right")


def test_each_set_uses_its_own_first_and_last_bay_not_global_panel_number():
    layout = _layout(3)
    layout = resize_receiving_sets(layout, set_count=2)
    layout = resize_receiving_bays(layout, set_index=1, bay_count=2)
    source = _source(layout)
    for si, bi, left, right in (
        (0, 0, False, True), (0, 1, True, True), (0, 2, True, False),
        (1, 0, False, True), (1, 1, True, False),
    ):
        body, _ = _body_for(source, si, bi)
        assert body.receiving_side_lock_participation == (left, right)


@pytest.mark.parametrize("invalid", ("wrong_set", "wrong_bay", "wrong_dimensions", "missing_identity"))
def test_invalid_or_unselected_multibay_identity_never_borrows_lock_holes(invalid):
    source = _source(_layout(3))
    selected = project_receiving_bay_legacy_aliases(source, set_index=0, bay_index=1)
    if invalid == "wrong_set":
        selected["_receiving_runtime_selection"]["set_id"] = "forged"
    elif invalid == "wrong_bay":
        selected["_receiving_runtime_selection"]["bay_id"] = "forged"
    elif invalid == "wrong_dimensions":
        selected["w"] += 50.0
    else:
        selected.pop("_receiving_runtime_selection")
    original = deepcopy(selected)
    with pytest.raises(ValueError, match="RECEIVING_SIDE_LOCK_"):
        api.build_box_body_operator_part_spec(
            selected, model_name="受電箱",
            fold_profile=selected["box_body_fold_profile"],
            structure_state=selected["box_body_structure_state"],
            snapshot=selected,
        )
    assert selected == original



def _factory_body():
    return dict(api.build_receiving_factory_confirmed_parts(
        {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0},
        confirmation="fresh_family_confirmed",
    ))["box_body"]


def test_factory_box_body_bind_real_set_bay_reuses_engine_joint_and_cutting():
    from ae_engine.sheetmetal_drawing import CirclePrimitive
    assert api.bind_receiving_factory_box_body_to_bay is __import__(
        "ae_engine", fromlist=["bind_receiving_factory_box_body_to_bay"]
    ).bind_receiving_factory_box_body_to_bay
    layout = _layout(3)
    original = _factory_body()
    assert original.receiving_side_lock_participation is None
    for bi, expected in enumerate(((False, True), (True, True), (True, False))):
        bound = api.bind_receiving_factory_box_body_to_bay(
            original, layout, set_index=0, bay_index=bi,
        )
        assert bound.receiving_side_lock_participation == expected
        assert api.bind_receiving_factory_box_body_to_bay(
            bound, layout, set_index=0, bay_index=bi,
        ) == bound
        rendered = api.build_box_body_structure_render_data(
            bound, ManufacturingContext(resource_root=ROOT),
        )
        for role, joined in (("left_side", expected[0]),
                             ("right_side", expected[1])):
            sheet = next(piece.render_data for piece in rendered.pieces
                         if piece.role == role)
            assert sheet.metadata["baseline_side_lock_participation"] is joined
            for radius, desired in ((5.25, 6 if joined else 0),
                                    (8.0, 2 if joined else 0)):
                assert sum(
                    isinstance(item, CirclePrimitive)
                    and item.layer == "CUTTING"
                    and abs(item.radius-radius) < 1e-6
                    for item in sheet.scene.primitives
                ) == desired
    assert original.receiving_side_lock_participation is None


def test_factory_box_body_bind_rejects_foreign_bay_without_mutation():
    from dataclasses import replace
    original = _factory_body()
    layout = _layout(3)
    with pytest.raises(ValueError, match="RECEIVING_FACTORY_BAY_SELECTION_INVALID"):
        api.bind_receiving_factory_box_body_to_bay(
            original, layout, set_index=0, bay_index=3,
        )
    with pytest.raises(ValueError, match="RECEIVING_FACTORY_BAY_DIMENSIONS_MISMATCH"):
        api.bind_receiving_factory_box_body_to_bay(
            replace(original, width=920.0), layout, set_index=0, bay_index=1,
        )
    wrong_side = replace(original, receiving_side_lock_participation=(True, False))
    with pytest.raises(ValueError, match="RECEIVING_FACTORY_BAY_LOCK_SOURCE_CONFLICT"):
        api.bind_receiving_factory_box_body_to_bay(
            wrong_side, layout, set_index=0, bay_index=0,
        )
    assert original.receiving_side_lock_participation is None


def test_grouped_output_rejects_unbound_factory_side_locks_and_accepts_bound(tmp_path):
    from ae_engine.contracts import ResolvedManufacturingGeometry, ResolvedManufacturingPart
    layout = _layout(2)
    body = _factory_body()
    base = {"model": "受電箱", "active_mode": "set_bay",
            "receiving_layout": layout, "t": 2.0}

    def provider(bind):
        def resolve(si, bi):
            spec = api.bind_receiving_factory_box_body_to_bay(
                body, layout, set_index=si, bay_index=bi,
            ) if bind else body
            rendered = api.build_box_body_structure_render_data(
                spec, ManufacturingContext(resource_root=ROOT),
            )
            return ResolvedManufacturingGeometry(parts=(
                ResolvedManufacturingPart("box_body", rendered),
            ))
        return resolve

    output = tmp_path / "reject"
    with pytest.raises(ValueError, match="RECEIVING_MULTIBAY_SIDE_LOCK_TOPOLOGY_MISMATCH"):
        api.export_grouped_receiving_multibay_dxf(
            base, physical_bay_geometry_provider=provider(False),
            flags={"box_body": True}, output_dir=output,
            group_mode="ALL", pre_commit_guard=lambda: None,
        )
    assert not tuple(output.rglob("*.dxf"))

    output = tmp_path / "verified"
    files = api.export_grouped_receiving_multibay_dxf(
        base, physical_bay_geometry_provider=provider(True),
        flags={"box_body": True}, output_dir=output,
        group_mode="ALL", pre_commit_guard=lambda: None,
    )
    # The verified ALL manufacturing file is now published atomically with
    # one independent total drawing across the same real physical Bays.
    assert len(files) == 2
    assert sum(name.endswith("全部.dxf") for name in files) == 1
    assert sum(name.endswith("總計.dxf") for name in files) == 1
    path = next(value for name, value in files.items() if name.endswith("全部.dxf"))
    total = next(value for name, value in files.items() if name.endswith("總計.dxf"))
    assert not ezdxf.readfile(total).audit().errors
    opened = ezdxf.readfile(path)
    assert not opened.audit().errors
    assert _cutting_radius_count(opened.modelspace(), 5.25) == 12
    assert _cutting_radius_count(opened.modelspace(), 8.0) == 4
