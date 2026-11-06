"""#2517: only Engine may turn CADSplit source dimensions into physical PartSpecs."""
from copy import deepcopy
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)

REPO = Path(__file__).resolve().parents[1]
SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}


def _build(outside, **kwargs):
    return manufacturing_api.build_receiving_factory_confirmed_parts(
        outside, **kwargs
    )


def test_fresh_confirmed_p1_source_to_five_physical_dxf_roundtrips(tmp_path):
    source = deepcopy(SOURCE)
    parts = _build(source, confirmation="fresh_family_confirmed")
    assert source == SOURCE
    assert [key for key, _ in parts] == ["box_body", "head", "tail"]
    body, head, tail = (item for _, item in parts)
    assert body.model_name == head.model_name == tail.model_name == "受電箱"
    assert (body.width, body.height, body.depth, body.thickness) == (
        800, 1600, 350, 2
    )
    assert (body.frame_width, body.zl1, body.zl2, body.zr2) == (
        29, -24, 24, 18
    )
    assert body.zr1 is None and body.z_comp is None
    assert body.fold_profile and body.back_panel_contract
    assert head.depth_comp_t == tail.depth_comp_t == 2.0
    assert (head.fold_left, head.fold_right, head.fold_top, head.fold_bottom) == (
        15, 15, 16, 15
    )

    bay = ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            panel_key="P1", source_revision="verified-p1", set_id="Set1", bay_id="Bay1"
        ),
        confirmed_parts=parts,
    )
    checks = []
    result = export_verified_resolved_integration_bays(
        (bay,), tmp_path / "manufactured",
        context=ManufacturingContext(resource_root=REPO),
        pre_commit_guard=lambda: checks.append("source-rechecked"),
    )
    assert checks == ["source-rechecked", "source-rechecked"]
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert len(result.output_files) == 5
    for output in result.output_files.values():
        drawing = ezdxf.readfile(output)
        layers = {entity.dxf.layer for entity in drawing.modelspace()}
        assert "CUTTING" in layers
        if "back" not in Path(output).stem:
            assert "BEND" in layers


def test_fresh_nondefault_source_dimensions_override_family_nominal_geometry():
    dimensions = {"w": 920.0, "h": 1770.0, "d": 410.0, "t": 2.5}
    parts = _build(dimensions, confirmation="fresh_family_confirmed")
    assert len(parts) == 3
    for _, spec in parts:
        assert (spec.width, spec.height, spec.depth, spec.thickness) == (
            920.0, 1770.0, 410.0, 2.5
        )
    assert parts[1][1].depth_comp_t == 2.0
    assert parts[0][1].model_name == "受電箱"


def test_saved_confirmed_engine_state_uses_actual_physical_profiles_not_fresh_fallback():
    source = deepcopy(SOURCE)
    saved = family_policy.apply_fresh_family_defaults({}, "受電箱")
    saved.update(source)
    saved["fw"] = 31.0
    saved["model"] = "受電箱"
    saved["box_body_structure_state"] = manufacturing_api.resolve_receiving_box_body_structure_state(None)
    saved["box_body_fold_profile"] = manufacturing_api.build_box_body_fold_profile(saved)
    saved["endcap_fold_profiles"] = {
        part: manufacturing_api.build_endcap_xy_fold_profiles(
            {**saved, "yl1": 19.0, "yr1": 21.0, "ytop1": 18.0},
            part_key=part,
        )
        for part in ("head", "tail")
    }
    saved["endcap_corner_policies"] = {
        part: family_policy.endcap_corner_policy(
            "受電箱", frame_width=saved["fw"], thickness=saved["t"],
            state=saved["box_body_structure_state"],
        )
        for part in ("head", "tail")
    }
    before = deepcopy(saved)
    parts = _build(source, confirmation="saved_operator_confirmed", operator_snapshot=saved)
    assert saved == before
    assert parts[0][1].frame_width == 31.0
    assert parts[1][1].fold_left == 19.0
    assert parts[2][1].fold_right == 21.0
    assert parts[1][1].fold_top == 18.0


@pytest.mark.parametrize("invalid", [
    {},
    {"w": 800, "h": 1600, "d": 350},
    {"w": 800, "h": 1600, "d": 350, "t": float("nan")},
    {"w": 800, "h": 1600, "d": 350, "t": False},
    {"w": 800, "h": 1600, "d": -350, "t": 2},
    {"w": 800, "h": 1600, "d": 350, "t": 2, "yl1": 15},
])
def test_reject_untrusted_or_manufacturing_source_fields(invalid):
    with pytest.raises((TypeError, ValueError), match="RECEIVING_SOURCE_DIMENSIONS_INVALID"):
        _build(invalid, confirmation="fresh_family_confirmed")


def test_source_only_does_not_authorize_manufacture_or_invent_state():
    with pytest.raises(ValueError, match="RECEIVING_OPERATOR_CONFIRMATION_REQUIRED"):
        _build(SOURCE)
    with pytest.raises(ValueError, match="RECEIVING_OPERATOR_CONFIRMATION_REQUIRED"):
        _build(SOURCE, confirmation="unconfirmed")
    with pytest.raises(ValueError, match="RECEIVING_OPERATOR_CONFIRMATION_AMBIGUOUS"):
        _build(
            SOURCE, confirmation="fresh_family_confirmed",
            operator_snapshot={"model": "受電箱"},
        )


def test_saved_state_must_match_source_and_contain_all_physical_authority():
    saved = {**SOURCE, "model": "受電箱", "fw": 29.0}
    with pytest.raises(ValueError, match="RECEIVING_SAVED_PHYSICAL_STATE_INCOMPLETE"):
        _build(
            SOURCE, confirmation="saved_operator_confirmed", operator_snapshot=saved
        )
    mismatch = {**saved, "w": 801.0}
    with pytest.raises(ValueError, match="RECEIVING_SOURCE_SAVED_DIMENSIONS_CONFLICT"):
        _build(
            SOURCE, confirmation="saved_operator_confirmed", operator_snapshot=mismatch
        )


def test_fresh_factory_confirmation_cannot_change_vault_or_export_source_only(tmp_path):
    from ae_engine.integration_api import (
        ManufacturingIntegrationRequest, dispatch_manufacturing_integration,
    )
    source = ManufacturingSourceIdentity("P1", "verified-p1", "Set1", "Bay1")
    response = dispatch_manufacturing_integration(ManufacturingIntegrationRequest(
        operation="export", family="受電箱", source=source,
    ))
    assert response.status == "EXTERNAL_EXPORT_NOT_CERTIFIED"
    assert not response.manufacturing_authorized
    assert not (tmp_path / "manufactured").exists()


def _confirmed_ordinary_base_snapshot():
    """Confirmed GUI project authority, not a CADSplit-made PartSpec."""
    from ae_engine.cabinet_types import policy as family_policy

    saved = family_policy.apply_fresh_family_defaults({}, "受電箱")
    saved.update(SOURCE)
    saved["model"] = "受電箱"
    saved["box_body_structure_state"] = manufacturing_api.resolve_receiving_box_body_structure_state(None)
    saved["box_body_fold_profile"] = manufacturing_api.build_box_body_fold_profile(saved)
    saved["endcap_fold_profiles"] = {
        role: manufacturing_api.build_endcap_xy_fold_profiles(saved, part_key=role)
        for role in ("head", "tail")
    }
    saved["endcap_corner_policies"] = {
        role: family_policy.endcap_corner_policy(
            "受電箱", frame_width=saved["fw"], thickness=saved["t"],
            state=saved["box_body_structure_state"],
        )
        for role in ("head", "tail")
    }
    saved["receiving_base_plate"] = {
        "pattern": "LEFT_FLAT_SIDE",
        "height": 340.0, "shrink_top": 20.0, "shrink_bottom": 20.0,
        "shrink_left": 45.0, "shrink_right": 45.0, "bend": 20.0,
    }
    return saved


def test_confirmed_source_api_adds_real_ordinary_base_and_reopens_six_dxfs(tmp_path):
    """New source->PartSpec->FinalScene->real DXF public Engine path."""
    from ae_engine.contracts import BasePlatePartSpec
    saved = _confirmed_ordinary_base_snapshot()
    unchanged = deepcopy(saved)
    specs = dict(_build(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, include_confirmed_base_plate=True,
    ))
    assert tuple(specs) == ("box_body", "head", "tail", "base_plate")
    assert isinstance(specs["base_plate"], BasePlatePartSpec)
    assert specs["base_plate"].receiving_bend_pattern == "LEFT_FLAT_SIDE"
    assert (specs["base_plate"].width, specs["base_plate"].height) == (800., 340.)
    assert saved == unchanged
    context = ManufacturingContext(resource_root=REPO)
    result = export_verified_resolved_integration_bays(
        (ManufacturingResolvedBayInput(
            family="受電箱",
            source=ManufacturingSourceIdentity("P1", "verified-src", "set-1", "bay-1"),
            source_dimensions_mm=SOURCE,
            operator_confirmation="saved_operator_confirmed",
            operator_snapshot=saved,
            include_confirmed_base_plate=True,
        ),),
        tmp_path / "output", context=context, pre_commit_guard=lambda: None,
    )
    assert result.physical_dxf_roundtrip_verified
    assert not result.complete_assembly_certified
    assert len(result.output_files) == 6
    base = next(
        Path(p) for p in result.output_files.values()
        if Path(p).name.endswith("base_plate.dxf")
    )
    document = ezdxf.readfile(base)
    assert document.audit().errors == []
    assert {"CUTTING", "BEND"} <= {
        entity.dxf.layer for entity in document.modelspace()
    }
    # Production output must be the same canonical API geometry as GUI uses.
    expected_render = manufacturing_api.build_operator_part_render_data(
        specs["base_plate"], context,
    )
    assert manufacturing_api.verify_saved_part_render_data_dxf(
        expected_render, base,
    ).ok


@pytest.mark.parametrize("variant,code", [
    ("fresh", "RECEIVING_FACTORY_BASE_REQUIRES_SAVED_OPERATOR_CONFIRMATION"),
    ("missing", "RECEIVING_FACTORY_CONFIRMED_BASE_SOURCE_REQUIRED"),
    ("center", "RECEIVING_FACTORY_ORDINARY_BASE_PATTERN_UNVERIFIED"),
    ("nfb", "RECEIVING_FACTORY_NFB_BASE_REQUIRES_VERIFIED_PAIR_API"),
    ("features", "RECEIVING_FACTORY_BASE_FEATURE_SOURCE_UNCONFIRMED"),
    ("invalid_selector", "RECEIVING_FACTORY_BASE_SELECTION_MUST_BE_BOOLEAN"),
])
def test_factory_base_api_rejects_unconfirmed_sources_before_any_dxf(
    variant, code, tmp_path,
):
    saved = _confirmed_ordinary_base_snapshot()
    if variant == "missing":
        del saved["receiving_base_plate"]
    if variant == "center":
        saved["receiving_base_plate"]["pattern"] = "CENTER_DOUBLE_SIDE_FOLD"
    if variant == "nfb":
        saved["nfb_config_submitted"] = True
    if variant == "features":
        saved["part_features"] = {"base_plate": [object()]}
    inclusion = 1 if variant == "invalid_selector" else True
    request = ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity("P1", "verified-src", "set-1", "bay-1"),
        source_dimensions_mm=SOURCE,
        operator_confirmation="fresh_family_confirmed" if variant == "fresh"
        else "saved_operator_confirmed",
        operator_snapshot=None if variant == "fresh" else saved,
        include_confirmed_base_plate=inclusion,
    )
    with pytest.raises(ValueError, match=code):
        export_verified_resolved_integration_bays(
            (request,), tmp_path / "blocked",
            pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "blocked").exists()



@pytest.mark.parametrize("role", ("head", "tail"))
def test_saved_factory_endcap_uses_same_original_boxbody_fold_api_as_gui(role):
    """RED before fix: factory EndCap lost both formed-FW assembly datums."""
    saved = _confirmed_ordinary_base_snapshot()
    before = deepcopy(saved)
    parts = dict(_build(
        SOURCE, confirmation="saved_operator_confirmed", operator_snapshot=saved,
    ))
    expected = manufacturing_api.formed_box_body_fw_widths(
        saved["box_body_fold_profile"], saved["t"],
    )
    assert expected[0] is not None and expected[1] is not None
    factory_spec = parts[role]
    assert (factory_spec.box_body_formed_fw_left,
            factory_spec.box_body_formed_fw_right) == expected

    # Same canonical Engine operation as the live WHD GUI, but sourcing the
    # exact confirmed physical Body Fold; CADSplit may not derive formed FW.
    gui_equivalent = manufacturing_api.build_endcap_operator_part_spec(
        {key: saved[key] for key in ("w", "h", "d", "t", "fw", "zl1")},
        model_name="受電箱", is_tail=(role == "tail"), holes=(),
        corner_policy=saved["endcap_corner_policies"][role],
        fold_profiles=saved["endcap_fold_profiles"][role],
        box_body_fold_profile=saved["box_body_fold_profile"],
        box_body_structure_state=saved["box_body_structure_state"],
    )
    assert factory_spec == gui_equivalent
    assert saved == before


def test_fresh_factory_head_tail_receive_real_engine_formed_fw_datum():
    confirmed = family_policy.apply_fresh_family_defaults(SOURCE, "受電箱")
    confirmed.update(SOURCE)
    expected_rows = manufacturing_api.build_box_body_fold_profile(confirmed)
    expected = manufacturing_api.formed_box_body_fw_widths(
        expected_rows, confirmed["t"],
    )
    parts = dict(_build(SOURCE, confirmation="fresh_family_confirmed"))
    for role in ("head", "tail"):
        assert (parts[role].box_body_formed_fw_left,
                parts[role].box_body_formed_fw_right) == expected


def test_verified_saved_factory_head_tail_dxfs_reopen_with_same_engine_datum(tmp_path):
    saved = _confirmed_ordinary_base_snapshot()
    parts = dict(_build(
        SOURCE, confirmation="saved_operator_confirmed", operator_snapshot=saved,
    ))
    context = ManufacturingContext(resource_root=REPO)
    output = export_verified_resolved_integration_bays(
        (ManufacturingResolvedBayInput(
            family="受電箱",
            source=ManufacturingSourceIdentity(
                "real-p1", "source-rev", "set-1", "bay-1",
            ),
            source_dimensions_mm=SOURCE,
            operator_confirmation="saved_operator_confirmed",
            operator_snapshot=saved,
        ),),
        tmp_path / "verified-parts", context=context,
        pre_commit_guard=lambda: None,
    )
    assert output.physical_dxf_roundtrip_verified
    assert output.complete_assembly_certified is False
    assert len(output.output_files) == 5
    for role in ("head", "tail"):
        path = next(
            Path(p) for p in output.output_files.values()
            if Path(p).name.endswith(f"{role}.dxf")
        )
        assert ezdxf.readfile(path).audit().errors == []
        canonical_render = manufacturing_api.build_operator_part_render_data(
            parts[role], context,
        )
        assert manufacturing_api.verify_saved_part_render_data_dxf(
            canonical_render, path,
        ).ok



def _physical_base_hole(*, offset=None, anchor=None, layer="CUTTING"):
    from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
    from ae_engine.sheetmetal_geometry import Vec2

    return CircleFeature(
        diameter=6.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE if anchor is None else anchor,
        offset=Vec2(400.0, 150.0) if offset is None else offset,
        layer=layer,
    )


def test_confirmed_saved_base_hole_source_reaches_real_verified_dxf(tmp_path):
    """RED before API: saved base CUTTING was rejected even when explicitly confirmed."""
    saved = _confirmed_ordinary_base_snapshot()
    hole = _physical_base_hole()
    saved["part_features"] = {"base_plate": [hole]}
    original = deepcopy(saved)
    source = {"base_plate": (hole,)}

    parts = dict(_build(
        SOURCE, confirmation="saved_operator_confirmed",
        operator_snapshot=saved, include_confirmed_base_plate=True,
        confirmed_base_plate_features=source,
    ))
    assert parts["base_plate"].features == (hole,)
    assert saved == original

    context = ManufacturingContext(resource_root=REPO)
    checks = []
    exported = export_verified_resolved_integration_bays(
        (ManufacturingResolvedBayInput(
            family="受電箱",
            source=ManufacturingSourceIdentity(
                "P1", "confirmed-source", "set-1", "bay-1",
            ),
            source_dimensions_mm=SOURCE,
            operator_confirmation="saved_operator_confirmed",
            operator_snapshot=saved,
            include_confirmed_base_plate=True,
            confirmed_base_plate_features=source,
        ),),
        tmp_path / "verified-with-hole", context=context,
        pre_commit_guard=lambda: checks.append("source-current"),
    )
    assert checks == ["source-current", "source-current"]
    assert exported.physical_dxf_roundtrip_verified
    assert exported.complete_assembly_certified is False
    assert len(exported.output_files) == 6
    base = next(
        Path(path) for path in exported.output_files.values()
        if Path(path).name.endswith("base_plate.dxf")
    )
    drawing = ezdxf.readfile(base)
    assert not drawing.audit().errors
    assert any(
        entity.dxftype() == "CIRCLE"
        and entity.dxf.layer == "CUTTING"
        and abs(float(entity.dxf.radius) - 3.0) <= 1e-6
        for entity in drawing.modelspace()
    )
    rendered = manufacturing_api.build_operator_part_render_data(
        parts["base_plate"], context,
    )
    assert manufacturing_api.verify_saved_part_render_data_dxf(
        rendered, base,
    ).ok


@pytest.mark.parametrize("variant,error", (
    ("missing_confirmation", "RECEIVING_FACTORY_BASE_FEATURE_SOURCE_UNCONFIRMED"),
    ("unsaved_extra_hole", "RECEIVING_FACTORY_BASE_FEATURE_SOURCE_UNCONFIRMED"),
    ("wrong_role", "RECEIVING_FACTORY_BASE_SOURCE_FEATURES_INVALID"),
    ("wrong_layer", "RECEIVING_FACTORY_BASE_SOURCE_FEATURES_INVALID"),
    ("wrong_anchor", "RECEIVING_FACTORY_BASE_SOURCE_FEATURES_INVALID"),
    ("no_base_selection", "RECEIVING_FACTORY_BASE_SELECTION_REQUIRED_FOR_FEATURES"),
    ("nfb_submitted", "RECEIVING_FACTORY_NFB_BASE_REQUIRES_VERIFIED_PAIR_API"),
))
def test_factory_base_hole_cannot_bypass_saved_source_or_physical_role(
    variant, error, tmp_path,
):
    from ae_engine.sheetmetal_feature_core import FeatureAnchor
    saved = _confirmed_ordinary_base_snapshot()
    hole = _physical_base_hole()
    saved["part_features"] = {"base_plate": [hole]}
    confirmed = {"base_plate": (hole,)}
    include = True
    if variant == "missing_confirmation":
        confirmed = None
    elif variant == "unsaved_extra_hole":
        saved["part_features"]["base_plate"] = []
    elif variant == "wrong_role":
        confirmed = {"head": (hole,)}
    elif variant == "wrong_layer":
        confirmed = {"base_plate": (_physical_base_hole(layer="MARKING"),)}
    elif variant == "wrong_anchor":
        confirmed = {"base_plate": (
            _physical_base_hole(anchor=FeatureAnchor.PANEL_CENTER),
        )}
    elif variant == "no_base_selection":
        include = False
    elif variant == "nfb_submitted":
        saved["nfb_config_submitted"] = True

    with pytest.raises(ValueError, match=error):
        export_verified_resolved_integration_bays(
            (ManufacturingResolvedBayInput(
                family="受電箱",
                source=ManufacturingSourceIdentity(
                    "P1", "confirmed-source", "set-1", "bay-1",
                ),
                source_dimensions_mm=SOURCE,
                operator_confirmation="saved_operator_confirmed",
                operator_snapshot=saved,
                include_confirmed_base_plate=include,
                confirmed_base_plate_features=confirmed,
            ),),
            tmp_path / "blocked", context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert not list(tmp_path.rglob("*.dxf"))


def test_confirmed_source_base_hole_outside_real_plate_cannot_commit(tmp_path):
    from ae_engine.sheetmetal_geometry import Vec2

    saved = _confirmed_ordinary_base_snapshot()
    outside = _physical_base_hole(offset=Vec2(10000.0, 10000.0))
    saved["part_features"] = {"base_plate": [outside]}
    with pytest.raises(ValueError, match="feature outside feature surface"):
        export_verified_resolved_integration_bays(
            (ManufacturingResolvedBayInput(
                family="受電箱",
                source=ManufacturingSourceIdentity(
                    "P1", "confirmed-source", "set-1", "bay-1",
                ),
                source_dimensions_mm=SOURCE,
                operator_confirmation="saved_operator_confirmed",
                operator_snapshot=saved,
                include_confirmed_base_plate=True,
                confirmed_base_plate_features={"base_plate": (outside,)},
            ),),
            tmp_path / "blocked", context=ManufacturingContext(resource_root=REPO),
            pre_commit_guard=lambda: None,
        )
    assert not list(tmp_path.rglob("*.dxf"))
