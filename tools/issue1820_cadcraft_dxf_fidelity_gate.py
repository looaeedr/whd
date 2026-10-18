"""#1820 independent, read-only DXF persistence gate for optional CADCraft tests.

Compares a source drawing to an isolated CADCraft-exported copy. Never repairs,
imports, or uses CADCraft output as WHD manufacturing authority. Fail closed.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

import ezdxf
from ezdxf.lldxf.encoding import decode_dxf_unicode

# Only entity families whose payloads are inventoried by _signature are
# accepted. A new kind is an explicit unsupported result, not a silent PASS.
SUPPORTED = frozenset({
    "LINE", "ARC", "CIRCLE", "LWPOLYLINE", "POLYLINE", "POINT",
    "TEXT", "MTEXT", "INSERT", "ATTRIB", "ATTDEF", "DIMENSION", "VERTEX", "SOLID",
})
# DXF version and declared codepage affect text decoding and block support.\n# Do not accept a CADCraft resave merely because its entity counts agree.\nHEADER_KEYS = ("$INSUNITS", "$MEASUREMENT", "$ACADVER", "$DWGCODEPAGE")
IGNORED = frozenset({"handle", "owner", "paperspace"})


def _value(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (tuple, list)):
        return [_value(part) for part in value]
    if isinstance(value, dict):
        return {str(k): _value(v) for k, v in sorted(value.items())}
    if hasattr(value, "x") and hasattr(value, "y"):
        return [_value(float(a)) for a in value]
    if hasattr(value, "__iter__"):
        return [_value(part) for part in value]
    # No opaque repr fallback: an unknown DXF payload must not pass silently.
    raise TypeError(f"UNSUPPORTED_DXF_VALUE: {type(value).__name__}")


def _signature(entity):
    kind = entity.dxftype()
    if kind not in SUPPORTED:
        raise ValueError(f"UNSUPPORTED_CADCRAFT_ENTITY: {kind}")
    attrs = {key: _value(value)
             for key, value in entity.dxfattribs().items()
             if key not in IGNORED}
    if kind == "INSERT":
        # DXF omitted 1.0 scale/0 rotation and explicit equivalents have
        # identical placement. Do not discard non-default transforms.
        for key, default in (
            ("xscale", 1.0), ("yscale", 1.0),
            ("zscale", 1.0), ("rotation", 0.0),
        ):
            attrs.setdefault(key, default)
        attrs["attribs"] = [_signature(attr) for attr in entity.attribs]
    elif kind in {"TEXT", "ATTRIB", "ATTDEF"}:
        if "text" in attrs:
            attrs["text"] = decode_dxf_unicode(attrs["text"])
    elif kind == "MTEXT":
        # MTEXT stores its content in entity.text, not a DXF attrib.
        attrs["mtext_content"] = decode_dxf_unicode(entity.text)
    elif kind == "LWPOLYLINE":
        attrs["vertices_xyseb"] = _value(list(entity.get_points("xyseb")))
        attrs["closed"] = bool(entity.closed)
    elif kind == "POLYLINE":
        attrs["vertices"] = [_signature(vertex) for vertex in entity.vertices]
        attrs["closed"] = bool(entity.is_closed)
    return json.dumps({"type": kind, "attrs": attrs},
                      ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _inventory(doc):
    """Read modelspace, block entities, and layers; unknown data is an error."""
    model = Counter(_signature(e) for e in doc.modelspace())
    blocks = Counter(
        (block.name, _signature(e))
        for block in doc.blocks
        if block.name.upper() not in {"*MODEL_SPACE", "*PAPER_SPACE"}
        for e in block
    )
    layers = Counter()
    for layer in doc.layers:
        attrs = {k: _value(v) for k, v in layer.dxfattribs().items()
                 if k not in IGNORED}
        for key in ("material_handle", "plotstyle_handle"):
            handle = layer.dxf.get(key, None)
            if handle is None:
                continue
            referenced = doc.entitydb.get(handle)
            if referenced is None:
                raise ValueError(f"UNRESOLVED_LAYER_REFERENCE {layer.dxf.name} {key}")
            # Handles are allocator IDs, not process/layer semantics.
            # Resolve referenced MATERIAL / plot-style object identity and
            # attributes, rather than treating handle renumbering as geometry.
            attrs[key] = {
                "entity_type": referenced.dxftype(),
                "attributes": {
                    k: _value(v) for k, v in referenced.dxfattribs().items()
                    if k not in IGNORED
                },
            }
        layers[json.dumps(attrs, sort_keys=True, ensure_ascii=False)] += 1
    return {"model": model, "blocks": blocks, "layers": layers}


def _delta(original, saved):
    removed = original - saved
    added = saved - original
    return {
        "removed": sum(removed.values()),
        "added": sum(added.values()),
        "removed_examples": [str(k)[:220] for k in list(removed.elements())[:4]],
        "added_examples": [str(k)[:220] for k in list(added.elements())[:4]],
    }


def audit(original: Path, resaved: Path):
    original, resaved = Path(original), Path(resaved)
    if original.resolve() == resaved.resolve():
        raise ValueError("ORIGINAL_MUST_NOT_BE_THE_RESAVED_DXF")
    source_sha = hashlib.sha256(original.read_bytes()).hexdigest()
    source = ezdxf.readfile(original)
    target = ezdxf.readfile(resaved)
    report = {
        "kind": "WHD_1820_CADCRAFT_DXF_READ_ONLY_FIDELITY_AUDIT",
        "source_sha256": source_sha,
        "resaved_sha256": hashlib.sha256(resaved.read_bytes()).hexdigest(),
        "header": {},
        "inventories": {},
        "failures": [],
    }
    for key in HEADER_KEYS:
        before, after = source.header.get(key), target.header.get(key)
        report["header"][key] = {"original": before, "resaved": after}
        if before != after:
            report["failures"].append(f"{key}_DRIFT")
    try:
        a, b = _inventory(source), _inventory(target)
        for category in ("model", "blocks", "layers"):
            change = _delta(a[category], b[category])
            report["inventories"][category] = change
            if change["removed"] or change["added"]:
                report["failures"].append(f"{category.upper()}_DIFF")
    except (TypeError, ValueError) as exc:
        report["failures"].append(f"UNSUPPORTED_OR_UNVERIFIED_DXF: {exc}")
    if hashlib.sha256(original.read_bytes()).hexdigest() != source_sha:
        report["failures"].append("SOURCE_MUTATED_DURING_AUDIT")
    report["result"] = "PASS" if not report["failures"] else "FAIL_CLOSED"
    report["scope"] = (
        "DXF units, version, codepage, modelspace entity attrs, blocks and layers. "
        "Not a raster-pixel parity test or permission to import into WHD."
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("cadcraft_saved_copy", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    report = audit(args.source, args.cadcraft_saved_copy)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    raise SystemExit(0 if report["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
