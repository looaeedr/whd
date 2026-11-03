"""#2517 Head/Tail and Door must share one confirmed CUTTING source boundary."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import inspect

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.integration_api import (
    ManufacturingSourceIdentity, ManufacturingResolvedBayInput,
    export_verified_resolved_integration_bays,
)
from ae_engine.contracts import ManufacturingContext
from ae_engine.sheetmetal_feature_core import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor,
)
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine import receiving_factory_requests as owner

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
COLUMNS = ((800.0, (1100.0, 500.0)),)
DOOR = "door_c1_r1"


def _circle(rotation=0):
    return CircleFeature(
        9.6, FeatureAnchor.ABSOLUTE_FINISHED_FACE, Vec2(400.0, 100.0),
        layer="CUTTING", rotation_deg=rotation,
    )


def _profile(layered):
    points = (Vec2(0.0, 0.0), Vec2(12.0, 0.0),
              Vec2(12.0, 8.0), Vec2(0.0, 8.0))
    return ProfileFeature(
        points=points, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(400.0, 100.0), layer="CUTTING",
        layered_profiles=(("MARKING", points, False),) if layered else (),
    )


def _bay(*, endcaps=None, doors=None):
    return ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            "P1", "confirmed-feature-scope", "Set1", "Bay1",
        ),
        source_dimensions_mm=SOURCE,
        operator_confirmation="fresh_family_confirmed",
        confirmed_endcap_features=endcaps,
        door_layout_columns=COLUMNS if doors is not None else (),
        confirmed_door_features=doors,
    )


@pytest.mark.parametrize("role", ("head", "tail"))
def test_confirmed_endcap_rejects_unapproved_secondary_marking_contour(role, tmp_path):
    source = {role: (_profile(layered=True),)}
    original = deepcopy(source)
    with pytest.raises(ValueError, match="RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="fresh_family_confirmed",
            confirmed_endcap_features=source,
        )
    assert source == original
    with pytest.raises(ValueError, match="RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID"):
        export_verified_resolved_integration_bays(
            (_bay(endcaps=source),), tmp_path / "rejected",
            pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "rejected").exists()


@pytest.mark.parametrize("role", ("head", "tail"))
@pytest.mark.parametrize("invalid_rotation", (True, False, 90.0, "90", None))
def test_confirmed_endcap_rejects_noncanonical_physical_rotation_source(
    role, invalid_rotation, tmp_path,
):
    source = {role: (_circle(rotation=invalid_rotation),)}
    original = deepcopy(source)
    with pytest.raises(ValueError, match="RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="fresh_family_confirmed",
            confirmed_endcap_features=source,
        )
    assert source == original
    with pytest.raises(ValueError, match="RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID"):
        export_verified_resolved_integration_bays(
            (_bay(endcaps=source),), tmp_path / "no-output",
            pre_commit_guard=lambda: None,
        )
    assert not (tmp_path / "no-output").exists()


@pytest.mark.parametrize("bad", (
    _profile(layered=True),
    _circle(rotation=True),
    RectFeature(
        width=20.0, height=15.0,
        anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(100.0, 100.0), rotation_deg=90.0,
    ),
))
def test_door_still_rejects_same_uncertified_physical_cutting(bad):
    with pytest.raises(ValueError, match="RECEIVING_DOOR_SOURCE_FEATURES_INVALID"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="fresh_family_confirmed",
            confirmed_door_layout_columns=COLUMNS,
            confirmed_door_features={DOOR: (bad,)},
        )


def test_real_endcap_and_door_confirmed_cutting_still_use_verified_engine_dxf(tmp_path):
    head_hole = _circle(rotation=0)
    door_hole = CircleFeature(
        diameter=13.75, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(100.0, 100.0), layer="CUTTING",
    )
    head = {"head": (head_hole,), "tail": ()}
    door = {DOOR: (door_hole,)}
    before = deepcopy((head, door))
    parts = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_endcap_features=head,
        confirmed_door_layout_columns=COLUMNS,
        confirmed_door_features=door,
    ))
    assert parts["head"].holes == (head_hole,)
    assert parts[DOOR].features == (door_hole,)
    assert (head, door) == before

    checked = []
    result = export_verified_resolved_integration_bays(
        (_bay(endcaps=head, doors=door),), tmp_path / "verified",
        pre_commit_guard=lambda: checked.append("source-current"),
        context=ManufacturingContext(resource_root=ROOT),
    )
    assert checked == ["source-current", "source-current"]
    assert result.physical_dxf_roundtrip_verified
    assert len(result.output_files) == 7
    files = tuple(Path(path) for path in result.output_files.values())
    head_files = [path for path in files if path.stem.endswith("head")]
    door_files = [path for path in files if path.stem.endswith(DOOR)]
    assert len(head_files) == len(door_files) == 1
    def radii(path):
        return [
            float(entity.dxf.radius)
            for entity in ezdxf.readfile(path).modelspace()
            if entity.dxftype() == "CIRCLE" and entity.dxf.layer == "CUTTING"
        ]
    assert any(abs(radius - 4.8) < 1e-6 for radius in radii(head_files[0]))
    assert any(abs(radius - 6.875) < 1e-6 for radius in radii(door_files[0]))
    assert (head, door) == before


def test_same_engine_source_guard_owns_both_endcap_and_door():
    shared = inspect.getsource(owner._confirmed_finished_face_cutting_features)
    door = inspect.getsource(owner._confirmed_door_source_features)
    assert "feature.layered_profiles" in shared
    assert "type(feature.rotation_deg) is not int" in shared
    assert "_confirmed_finished_face_cutting_features(" in door
    assert "item.layered_profiles" not in door
    assert "type(item.rotation_deg)" not in door
