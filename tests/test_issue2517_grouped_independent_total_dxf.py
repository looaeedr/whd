"""#2517: a separate, atomically committed total machining DXF."""
from __future__ import annotations

from tempfile import TemporaryDirectory

import ezdxf
import pytest

from ae_engine import manufacturing_api
from ae_engine.manufacturing_export import receiving_instance_namespace
from ae_engine.receiving_dxf_groups import commit_verified_receiving_groups
from tests.test_issue2690_composed_panel_dxf import _flat, _geometry
from tests.test_issue2692_receiving_grouped_dxf import _seven


@pytest.fixture(autouse=True)
def _fixed_stamp(monkeypatch):
    monkeypatch.setattr(
        "ae_engine.receiving_dxf_groups._taipei_output_stamp",
        lambda: "202611071258",
    )


def _seven_physical_doors(layout):
    output = []
    index = 0
    for group in layout["sets"]:
        for bay in group["bays"]:
            namespace = receiving_instance_namespace(
                set_id=group["stable_id"], bay_id=bay["stable_id"],
            )
            # P3 deliberately has identical dimensions but different holes.
            render = _flat("door", width=90, hole=index != 2)
            output.append((namespace, "door", f"{namespace}__door.dxf", render))
            index += 1
    return tuple(output)


def _machining_counts(path):
    doc = ezdxf.readfile(path)
    assert not doc.audit().errors
    entities = tuple(doc.modelspace())
    outlines = sum(
        e.dxftype() == "LWPOLYLINE" and e.dxf.layer == "CUTTING"
        for e in entities
    )
    holes = sum(
        e.dxftype() == "CIRCLE" and e.dxf.layer == "CUTTING"
        for e in entities
    )
    labels = tuple(
        e.plain_text()
        for e in entities
        if e.dxftype() == "MTEXT" and e.dxf.layer == "CHECK"
    )
    return outlines, holes, labels


@pytest.mark.parametrize("mode,groups", [
    ("ALL", ("全部",)),
    ("PER_SET", ("第1套", "第2套")),
    ("END_VS_MIDDLE", ("頭尾盤", "中間盤")),
])
def test_one_independent_total_dxf_across_all_bays_without_changing_group_flats(
    tmp_path, mode, groups,
):
    layout = _seven()
    rows = _seven_physical_doors(layout)
    with TemporaryDirectory(dir=tmp_path) as staging:
        result = commit_verified_receiving_groups(
            layout, mode, rows, staging, tmp_path / "out",
            pre_commit_guard=lambda: None,
        )
    prefix = "202611071258_p1~p7"
    assert set(result) == {
        *(prefix + name + ".dxf" for name in groups),
        prefix + "總計.dxf",
    }
    assert {path.name for path in (tmp_path / "out").glob("*.dxf")} == set(result)
    membership = {
        "全部": (0, 1, 2, 3, 4, 5, 6),
        "第1套": (0, 1, 2, 3),
        "第2套": (4, 5, 6),
        "頭尾盤": (0, 3, 4, 6),
        "中間盤": (1, 2, 5),
    }
    for name in groups:
        filename = prefix + name + ".dxf"
        outlines, holes, _labels = _machining_counts(result[filename])
        assert outlines == len(membership[name])
        assert holes == sum(index != 2 for index in membership[name])
    outlines, holes, labels = _machining_counts(result[prefix + "總計.dxf"])
    assert (outlines, holes) == (2, 1)
    assert "總計：7片；同板件同孔位 2 種" in labels
    assert "door × 6" in labels and "door × 1" in labels
    assert "door（式樣1） × 6：P1, P2, P4, P5, P6, P7" in labels
    assert "door（式樣2） × 1：P3" in labels


def test_total_is_part_of_atomic_batch_and_does_not_replace_existing_outputs(
    tmp_path, monkeypatch,
):
    import ae_engine.composed_panel_dxf as composer

    layout = _seven()
    rows = _seven_physical_doors(layout)
    root = tmp_path / "out"
    root.mkdir()
    originals = {
        "202611071258_p1~p7第1套.dxf": b"original-set",
        "202611071258_p1~p7總計.dxf": b"original-total",
    }
    for name, data in originals.items():
        (root / name).write_bytes(data)
    save_original = composer.save_composed_panel_dxf

    def fail_only_total(*args, **kwargs):
        if kwargs.get("compact_quantity_total"):
            raise ValueError("TOTAL_DXF_FAILED_BEFORE_COMMIT")
        return save_original(*args, **kwargs)

    monkeypatch.setattr(composer, "save_composed_panel_dxf", fail_only_total)
    with TemporaryDirectory(dir=tmp_path) as staging:
        with pytest.raises(ValueError, match="TOTAL_DXF_FAILED_BEFORE_COMMIT"):
            commit_verified_receiving_groups(
                layout, "PER_SET", rows, staging, root,
                pre_commit_guard=lambda: None, overwrite=True,
            )
    assert {p.name for p in root.glob("*.dxf")} == set(originals)
    assert all((root / n).read_bytes() == data for n, data in originals.items())


def test_total_requires_boolean_flag_and_real_quantity_mode(tmp_path):
    panels = (("P1", _geometry(("door", _flat("door")))),)
    path = tmp_path / "bad.dxf"
    with pytest.raises(TypeError, match="COMPACT_TOTAL_FLAG_MUST_BE_BOOL"):
        manufacturing_api.save_composed_panel_dxf(
            panels, path, pre_commit_guard=lambda: None,
            quantity_summary=True, compact_quantity_total="yes",
        )
    with pytest.raises(ValueError, match="REQUIRES_QUANTITY_SUMMARY"):
        manufacturing_api.save_composed_panel_dxf(
            panels, path, pre_commit_guard=lambda: None,
            compact_quantity_total=True,
        )
    assert not path.exists()
