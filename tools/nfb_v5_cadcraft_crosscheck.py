# -*- coding: utf-8 -*-
"""Cross-check a WHD *trial-only* real NFB V5 FinalScene with CADCraft CLI.

emit: WHD builds a genuine inner-door panel and adds V5 numeric holes, then
      serializes its DrawingScene as a CI-only DXF (never via release API).
verify: CADCraft must successfully open and re-save that DXF. ezdxf then
        independently compares *all* model-space primitives and layer/colors
        with the original WHD DXF, and the original must match CSV geometry.

This tool does not export any customer/manufacturing file or sign off parts.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import ezdxf

from ae_engine.cabinet_types import policy as cabinet_family_policy
from ae_engine.cabinet_types.receiving import apply_family_defaults
from ae_engine.dxf_serialization import save_scene_dxf
from ae_engine.manufacturing_api import build_inner_door_panel_render_data
from ae_engine.receiving_nfb_numeric_catalog import model_spec
from ae_engine.receiving_nfb_numeric_panel_projection import NfbPanelDatum
from ae_engine.receiving_nfb_v5_real_part_cutting import trial_v5_numeric_cutting_on_real_part

BRAND, MODEL = "士林", "2P125SN"
KIND = "WHD_NFB_V5_CI_UNVERIFIED_CADCRAFT_ROUNDTRIP"


def _fixture():
    state = apply_family_defaults({
        "model": "受電箱", "w": 800.0, "h": 1600.0, "d": 350.0,
        "t": 2.0, "fw": 29.0, "door_gap_w": 3.5, "door_gap_h": 3.5,
    })
    state.update({
        "multi_door_enabled": True,
        "door_layout_scope": "receiving-main",
        "door_layout_columns": [[800.0, [1100.0, 500.0]]],
        "inner_doors": [{
            "stable_id": "upper", "cell_key": "0:0",
            "included_frame_sides": ["top", "left", "right"],
        }],
    })
    panel = next(p for p in cabinet_family_policy.derive_inner_door_panels(state)
                 if p.inner_door_id == "upper")
    baseline = build_inner_door_panel_render_data(panel)
    face_width = panel.unfolded_width - panel.fold_left - panel.fold_right
    face_height = panel.unfolded_height - panel.fold_bottom - panel.fold_top
    # The centre here comes from the actual inner-door unfold; this fixture
    # does NOT claim that the operator's world X/Y or real switch row equals it.
    datum = NfbPanelDatum(
        panel.stable_id, "inner-door",
        (panel.fold_left + face_width / 2,
         panel.fold_bottom + face_height / 2),
        (1, 0), (0, 1),
    )
    return baseline, datum


def _rounded(v):
    return round(float(v), 5)


def _cycles(points):
    """Normalize a closed contour across rotation and reverse vertex order."""
    a = tuple((_rounded(x), _rounded(y)) for x, y in points)
    if len(a) > 1 and a[0] == a[-1]:
        a = a[:-1]
    if len(a) < 3:
        raise ValueError("Invalid DXF closed contour")
    return min(
        tuple(sequence[pos:] + sequence[:pos])
        for sequence in (a, a[::-1]) for pos in range(len(a))
    )


def _entities(path):
    """Canonical geometry and process-layer inventory for *every* DXF entity."""
    doc = ezdxf.readfile(path)
    result = Counter()
    for ent in doc.modelspace():
        typ = ent.dxftype()
        layer = str(ent.dxf.layer)
        color = int(ent.dxf.get("color", 256))
        if typ == "LWPOLYLINE":
            if not ent.closed:
                raise ValueError("Unclosed WHD/CADCraft modelspace LWPOLYLINE")
            if any(abs(float(row[4])) > 1e-9 for row in ent.get_points("xyseb")):
                raise ValueError("Unexpected curved WHD/CADCraft LWPOLYLINE")
            shape = _cycles(ent.get_points("xy"))
        elif typ == "CIRCLE":
            shape = (
                _rounded(ent.dxf.center.x), _rounded(ent.dxf.center.y),
                _rounded(ent.dxf.radius),
            )
        elif typ == "LINE":
            shape = tuple(sorted((
                (_rounded(ent.dxf.start.x), _rounded(ent.dxf.start.y)),
                (_rounded(ent.dxf.end.x), _rounded(ent.dxf.end.y)),
            )))
        else:
            raise ValueError(f"Unsupported DXF entity {typ}: fail closed")
        result[(typ, layer, color, shape)] += 1
    if not result:
        raise ValueError("CADCraft check cannot pass an empty drawing")
    return result


def _expected_holes(datum):
    spec = model_spec(BRAND, MODEL)
    if spec is None or not spec.dimensionally_complete:
        raise ValueError("V5 fixture model incomplete")
    opening = _cycles(datum.map_xy(p) for p in spec.opening_corners_xy_mm)
    screws = tuple((
        _rounded(datum.map_xy(p)[0]), _rounded(datum.map_xy(p)[1]),
        _rounded(spec.screw_diameter_mm / 2),
    ) for p in spec.screw_centers_xy_mm)
    return opening, screws


def emit(dxf: Path, manifest: Path):
    baseline, datum = _fixture()
    candidate = trial_v5_numeric_cutting_on_real_part(
        baseline, datum=datum, brand=BRAND, model=MODEL, feature="both",
    )
    if (candidate.manufacturing_ready or
            candidate.render_data.metadata.get("nfb_trial_export_approved") is not False):
        raise ValueError("NFB V5 fixture must remain NON-MANUFACTURABLE")
    if candidate.render_data.material.area >= baseline.material.area:
        raise ValueError("No actual V5 material removed")
    dxf.parent.mkdir(parents=True, exist_ok=True)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    save_scene_dxf(dxf, candidate.render_data.scene)  # CI artifact only
    entities = _entities(dxf)
    opening, screws = _expected_holes(datum)
    if entities[("LWPOLYLINE", "CUTTING", 3, opening)] != 1:
        raise ValueError("WHD opening does not match V5 numbers")
    for hole in screws:
        if entities[("CIRCLE", "CUTTING", 3, hole)] != 1:
            raise ValueError("WHD screw holes do not match V5 numbers")
    manifest.write_text(json.dumps({
        "kind": KIND, "brand": BRAND, "model": MODEL, "part_id": datum.part_id,
        "dxf_sha256": hashlib.sha256(dxf.read_bytes()).hexdigest(),
        "opening_uv": opening, "screws_uv_radius": screws,
        "original_entity_count": sum(entities.values()),
        "manufacturing_ready": False,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"TEST_ONLY_NFB_V5_DXF {dxf} {sum(entities.values())} entities")


def verify(original: Path, roundtrip: Path, manifest: Path, info_path: Path):
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if (data.get("kind") != KIND or data.get("manufacturing_ready") is not False
            or data.get("dxf_sha256") != hashlib.sha256(original.read_bytes()).hexdigest()):
        raise ValueError("Unverified source/manifest identity mismatch")
    info = json.loads(info_path.read_text(encoding="utf-8"))
    if not isinstance(info, dict) or not info:
        raise ValueError("CADCraft did not produce a valid drawing.inspect result")
    source = _entities(original)
    reopened = _entities(roundtrip)
    if reopened != source:
        removed = source - reopened
        added = reopened - source
        raise ValueError(
            "CADCRAFT_DXF_GEOMETRY_OR_LAYER_DIFF: "
            + repr({"removed": list(removed.elements())[:8], "added": list(added.elements())[:8]})
        )
    # This is the trial's full native DXF, not just a manually constructed
    # five-entity sample. Re-save must preserve the panel and its BEND lines.
    expected_opening = _cycles(data["opening_uv"])
    if source[("LWPOLYLINE", "CUTTING", 3, expected_opening)] != 1:
        raise ValueError("V5 CUTTING rectangle lost")
    for x, y, radius in data["screws_uv_radius"]:
        if source[("CIRCLE", "CUTTING", 3, (_rounded(x), _rounded(y), _rounded(radius)))] != 1:
            raise ValueError("V5 CUTTING screw circle lost")
    if not any(layer == "BEND" for typ, layer, color, shape in source):
        raise ValueError("Actual physical BEND baseline missing")
    print("CADCRAFT_V5_REAL_FINALSCENE_ROUNDTRIP_PASS",
          len(source), "distinct records", sum(source.values()), "entities")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    producer = sub.add_parser("emit")
    producer.add_argument("dxf", type=Path)
    producer.add_argument("manifest", type=Path)
    verifier = sub.add_parser("verify")
    verifier.add_argument("original", type=Path)
    verifier.add_argument("roundtrip", type=Path)
    verifier.add_argument("manifest", type=Path)
    verifier.add_argument("info_path", type=Path)
    args = parser.parse_args()
    if args.action == "emit":
        emit(args.dxf, args.manifest)
    else:
        verify(args.original, args.roundtrip, args.manifest, args.info_path)


if __name__ == "__main__":
    main()
