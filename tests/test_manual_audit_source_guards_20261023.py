# -*- coding: utf-8 -*-
"""Real source invariants found by reading R4–R6 code, not CI-only smoke."""
from math import nan
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine.assembly_marking_geometry import (
    _normalize, backproject_mapped_skin_world_points, vector_unit,
)
from ae_engine.baseline_source import baseline_cutting_bounds
from ae_engine.dxf_acceptance import _circle_rows_close, _rows_close
from phase6_manufacturing_geometry import (
    _phase6_assembly_placement_for_part, _phase6_signature_canonical_value,
)


def test_backprojection_uses_real_planar_affine_fallback_outside_triangle():
    source = SimpleNamespace(
        world=((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)),
        flat=((0., 0.), (1., 0.), (0., 1.)),
    )
    result = backproject_mapped_skin_world_points((source,), ((2., .25, 0.),))
    assert result.status == "RESOLVED"
    assert result.flat_points[0] == pytest.approx((2., .25))


def test_backprojection_invalid_source_or_point_fails_closed():
    good = SimpleNamespace(
        world=((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)),
        flat=((0., 0.), (1., 0.), (0., 1.)),
    )
    bad = SimpleNamespace(
        world=((0.,), (1., 0., 0.), (0., 1., 0.)), flat=good.flat,
    )
    for source, pt in ((good, (nan, 0., 0.)),
                       (good, (1., 2.)), (bad, (.3, .1, 0.))):
        result = backproject_mapped_skin_world_points((source,), (pt,))
        assert result.status == "SKIPPED_FAIL_CLOSED"
        assert result.flat_points == ()


@pytest.mark.parametrize("tolerance", (0., -.1, nan))
def test_vector_unit_rejects_invalid_tolerance(tolerance):
    with pytest.raises(ValueError):
        _normalize((1., 0., 0.), tolerance)
    with pytest.raises(ValueError):
        vector_unit((1., 0., 0.), tolerance=tolerance)


def test_near_coincident_bend_lines_require_full_unique_matching():
    expected = (("x", 0., 10., 20.), ("x", .75, 10., 20.))
    actual = (("x", .5, 10., 20.), ("x", 0., 10., 20.))
    assert _rows_close(expected, actual, .6)
    assert not _rows_close(expected, (actual[0], ("x", 2., 10., 20.)), .6)


def test_near_coincident_cutting_holes_require_full_unique_matching():
    expected = ((0., 20., 5.), (.75, 20., 5.))
    actual = ((.5, 20., 5.), (0., 20., 5.))
    assert _circle_rows_close(expected, actual, .6)
    assert not _circle_rows_close(expected, (actual[0], (2., 20., 5.)), .6)
    assert not _circle_rows_close(((nan, 20., 5.),), ((0., 20., 5.),), 1.)


def test_real_dxf_bounds_reject_one_corrupted_structural_entity():
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(((0., 0.), (100., 0.), (100., 50.), (0., 50.)),
                       close=True, dxfattribs={"layer": "CUTTING"})
    assert baseline_cutting_bounds(msp) == pytest.approx((0., 0., 100., 50.))

    class DamagedLine:
        dxf = SimpleNamespace(
            layer="CUTTING",
            start=SimpleNamespace(x=1., y=nan),
            end=SimpleNamespace(x=nan, y=2.),
        )

        def dxftype(self):
            return "LINE"

    assert baseline_cutting_bounds((*msp, DamagedLine())) is None


def test_real_assembly_placement_does_not_mask_invalid_offset_with_origin():
    part = "box_body:divider:demo:VERTICAL:C0_C1"
    for offset in ((), (1., 2.), (0., nan, 0.), (True, 0., 0.)):
        snapshot = {"model": "一般箱", "workspace": {
            "assembly_placements": {
                part: {"placement_kind": "offset", "world_offset": offset},
            },
        }}
        with pytest.raises(ValueError, match="assembly offset"):
            _phase6_assembly_placement_for_part(snapshot, part)


def test_nonfinite_manufacturing_inputs_never_alias_literal_cache_key():
    assert _phase6_signature_canonical_value("__NaN__") == "__NaN__"
    for invalid in (nan, {"part": (float("inf"),)}):
        with pytest.raises(ValueError, match="nonfinite manufacturing signature"):
            _phase6_signature_canonical_value(invalid)
    assert _phase6_signature_canonical_value((1, 2.)) == (1., 2.)

@pytest.mark.parametrize("bad", [True, False])
def test_r6_96_mapped_skin_world_point_never_accepts_boolean_millimetres(bad):
    """A saved boolean cannot be interpreted as X=1 or X=0 in 3D MARKING."""
    source = SimpleNamespace(
        world=((0., 0., 0.), (1., 0., 0.), (0., 1., 0.)),
        flat=((0., 0.), (1., 0.), (0., 1.)),
    )
    assert backproject_mapped_skin_world_points((source,), ((.25, .25, 0.),)).status == "RESOLVED"
    result = backproject_mapped_skin_world_points((source,), ((bad, 0., 0.),))
    assert result.status == "SKIPPED_FAIL_CLOSED"
    assert result.flat_points == ()


def test_r6_96_world_vector_and_tolerance_refuse_boolean_inputs():
    with pytest.raises(ValueError, match="degenerate vector"):
        _normalize((True, 0., 0.), 1e-6)
    with pytest.raises(ValueError):
        vector_unit((2., 0., 0.), tolerance=True)
    assert vector_unit((2., 0., 0.), tolerance=1e-6) == (1., 0., 0.)

@pytest.mark.parametrize("bad", ["false", "true", 0, 1, None, (), [], {}])
def test_r6_98_joint_marking_activation_is_exact_boolean_not_python_truthiness(bad):
    from ae_engine.contracts import JointMarkingProductionStatus

    with pytest.raises(ValueError, match="activation_enabled must be boolean"):
        JointMarkingProductionStatus(
            gate_state="FOUNDATION_MERGED",
            activation_enabled=bad,
            export_disposition="UNRESOLVED",
            production_policy_count=0,
        )


def test_r6_98_valid_joint_marking_activation_keeps_actual_dormant_gate_state():
    from ae_engine.contracts import JointMarkingProductionStatus

    for enabled in (False, True):
        status = JointMarkingProductionStatus(
            gate_state="FOUNDATION_MERGED",
            activation_enabled=enabled,
            export_disposition="UNRESOLVED",
            production_policy_count=0,
        )
        assert status.activation_enabled is enabled
        assert status.production_policy_count == 0
