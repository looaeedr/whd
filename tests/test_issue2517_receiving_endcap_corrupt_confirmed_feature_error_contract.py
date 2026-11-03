"""#2517 malformed confirmed Head/Tail geometry must fail with the Engine code."""
from __future__ import annotations

from copy import deepcopy
import inspect
from pathlib import Path

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine import receiving_factory_requests as source_owner
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput, ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from ae_engine.sheetmetal_feature_core import (
    CircleFeature, RectFeature, ProfileFeature, FeatureAnchor,
)
from ae_engine.sheetmetal_geometry import Vec2


SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
CODE = "RECEIVING_ENDCAP_SOURCE_FEATURES_INVALID"


def _circle(offset=Vec2(400.0, 100.0), *, diameter=9.6):
    return CircleFeature(
        diameter, FeatureAnchor.ABSOLUTE_FINISHED_FACE, offset,
        layer="CUTTING",
    )


def _broken_features():
    return (
        _circle(None),  # Direct untyped caller bypasses dataclass annotation
        _circle(object()),
        _circle(Vec2(10**400, 100.0)),  # float(int) would raise OverflowError
        _circle(diameter=10**400),
        RectFeature(
            10**400, 10.0, FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            Vec2(100.0, 100.0), layer="CUTTING",
        ),
        ProfileFeature(
            points=None, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(400.0, 100.0), layer="CUTTING",
        ),
        ProfileFeature(
            points=(Vec2(0, 0), Vec2(10, 0), object()),
            anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
            offset=Vec2(400.0, 100.0), layer="CUTTING",
        ),
    )


def _bay(features):
    return ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            "P1", "malformed-source-rejection", "Set1", "Bay1",
        ),
        source_dimensions_mm=SOURCE,
        operator_confirmation="fresh_family_confirmed",
        confirmed_endcap_features=features,
    )


@pytest.mark.parametrize("role", ("head", "tail"))
@pytest.mark.parametrize("bad", _broken_features())
def test_corrupt_typed_endcap_source_has_one_public_error_and_no_dxf_output(
    role, bad, tmp_path,
):
    features = {role: (bad,)}
    with pytest.raises(ValueError, match=f"^{CODE}$"):
        api.build_receiving_factory_confirmed_parts(
            SOURCE, confirmation="fresh_family_confirmed",
            confirmed_endcap_features=features,
        )
    output = tmp_path / f"rejected-{role}"
    with pytest.raises(ValueError, match=f"^{CODE}$"):
        export_verified_resolved_integration_bays(
            (_bay(features),), output,
            pre_commit_guard=lambda: None,
        )
    assert not output.exists()


@pytest.mark.parametrize("role", ("head", "tail"))
def test_ordinary_confirmed_endcap_source_preserves_verified_dxf_readback(
    role, tmp_path,
):
    feature = _circle()
    source = {role: (feature,)}
    before = deepcopy(source)
    specs = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_endcap_features=source,
    ))
    assert specs[role].holes == (feature,)
    assert source == before
    output = export_verified_resolved_integration_bays(
        (_bay(source),), tmp_path / "verified",
        context=ManufacturingContext(resource_root=Path(__file__).resolve().parents[1]),
        pre_commit_guard=lambda: None,
    )
    assert output.physical_dxf_roundtrip_verified
    assert len(output.output_files) == 5
    target = next(
        Path(v) for v in output.output_files.values()
        if Path(v).stem.endswith(role)
    )
    circles = [
        e for e in ezdxf.readfile(target).modelspace()
        if e.dxftype() == "CIRCLE" and e.dxf.layer == "CUTTING"
    ]
    assert any(abs(float(e.dxf.radius) - 4.8) < 1e-6 for e in circles)


def test_shared_geometry_checks_stay_single_engine_owner_with_role_specific_codes():
    head_guard = inspect.getsource(source_owner._confirmed_endcap_source_features)
    door_guard = inspect.getsource(source_owner._confirmed_door_source_features)
    assert "_confirmed_finished_face_cutting_features(" in head_guard
    assert "_confirmed_finished_face_cutting_features(" in door_guard
    assert "except (AttributeError, TypeError, ValueError, OverflowError)" in head_guard
    assert CODE in head_guard
    assert "RECEIVING_DOOR_SOURCE_FEATURES_INVALID" in door_guard
