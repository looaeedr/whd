"""#2517 acceptance: GUI and confirmed Receiving source produce the same Door DXF.

Unlike a Factory-only PartSpec test, this executes the real WHD GUI adapter
and the independent confirmed-source Engine request, then cross-verifies
their separately saved physical DXF outputs. No Tk presentation or mocks of
manufacturing geometry are involved.
"""
from pathlib import Path
from types import SimpleNamespace

import ezdxf
import pytest

from ae_engine import manufacturing_api as api
from ae_engine.cabinet_types import policy as family_policy
from ae_engine.contracts import ManufacturingContext
from ae_engine.integration_api import (
    ManufacturingResolvedBayInput,
    ManufacturingSourceIdentity,
    export_verified_resolved_integration_bays,
)
from ae_engine.sheetmetal_feature_core import CircleFeature, FeatureAnchor
from ae_engine.sheetmetal_geometry import Vec2
from ae_engine.sheetmetal_part_adapters import derive_door_layout_cells
from gui_modules.application import manufacturing_adapter as gui

ROOT = Path(__file__).resolve().parents[1]
SOURCE = {"w": 800.0, "h": 1600.0, "d": 350.0, "t": 2.0}
COLUMNS = ((800.0, (1100.0, 500.0)),)
UPPER = "door_c1_r1"
LOWER = "door_c1_r2"


def _hole():
    return CircleFeature(
        diameter=13.75, anchor=FeatureAnchor.ABSOLUTE_FINISHED_FACE,
        offset=Vec2(100.0, 100.0), layer="CUTTING",
    )


def _gui_door_part_spec(cell, values, unfolded_features):
    """Invoke the shipped GUI adapter, forwarding source into its Engine API."""
    key = f"{cell.column_index}:{cell.row_index}"
    host = SimpleNamespace(
        door_layout_indicator_states={key: {"mode": "none"}},
        door_layout_features={key: list(unfolded_features)},
        _door_layout_cell_key=lambda selected: (
            f"{selected.column_index}:{selected.row_index}"
        ),
        _baseline_source_model=lambda: "受電箱",
        _manual_corner_policy=lambda *_args: None,
        _door_material_frame_width=lambda fw, t: api.door_material_frame_width(
            "受電箱", frame_width=fw, thickness=t,
        ),
        door_nameplate_center_datum_top=None,
    )
    host._door_part_spec_from_values = (
        lambda data, **kwargs: gui._door_part_spec_from_values(
            host, data, **kwargs,
        )
    )
    return gui._door_layout_part_spec(host, cell, values)


@pytest.mark.parametrize("confirmed_features", (False, True))
def test_actual_receiving_gui_door_and_source_factory_have_same_dxf(
    tmp_path, confirmed_features,
):
    features = {UPPER: (_hole(),)} if confirmed_features else {}
    original = ManufacturingResolvedBayInput(
        family="受電箱",
        source=ManufacturingSourceIdentity(
            panel_key="P1", source_revision="confirmed-p1",
            set_id="Set1", bay_id="Bay1",
        ),
        source_dimensions_mm=SOURCE,
        operator_confirmation="fresh_family_confirmed",
        door_layout_columns=COLUMNS,
        confirmed_door_features=features,
    )
    context = ManufacturingContext(resource_root=ROOT)
    verified = export_verified_resolved_integration_bays(
        (original,), tmp_path / "factory",
        context=context, pre_commit_guard=lambda: None,
    )
    assert verified.physical_dxf_roundtrip_verified
    assert not verified.complete_assembly_certified
    assert len(verified.output_files) == 7

    parts = dict(api.build_receiving_factory_confirmed_parts(
        SOURCE, confirmation="fresh_family_confirmed",
        confirmed_door_layout_columns=COLUMNS,
        confirmed_door_features=features,
    ))
    operator = family_policy.apply_fresh_family_defaults(SOURCE, "受電箱")
    operator.update(SOURCE)
    cells = derive_door_layout_cells(COLUMNS)
    assert tuple(parts) == ("box_body", "head", "tail", UPPER, LOWER)

    for cell, key in zip(cells, (UPPER, LOWER)):
        from_source = parts[key]
        gui_features = api.map_door_features_to_unfolded_material(
            from_source, context,
        )
        from_gui = _gui_door_part_spec(cell, operator, gui_features)
        assert from_gui.feature_space == "legacy_unfolded"
        assert from_source.feature_space == "finished_face"
        assert from_gui.model_name == from_source.model_name == "受電箱"
        assert from_gui.frame_edges == from_source.frame_edges
        assert from_gui.features == gui_features

        factory_render = api.build_operator_part_render_data(
            from_source, context,
        )
        gui_render = api.build_operator_part_render_data(
            from_gui, context,
        )
        # Actual canonical Final Material must match, not just PartSpec labels.
        assert factory_render.material.equals(gui_render.material)

        actual_path = next(
            Path(path) for path in verified.output_files.values()
            if Path(path).name.endswith(f"{key}.dxf")
        )
        gui_path = tmp_path / f"gui-{key}.dxf"
        api.save_part_render_data_dxf(
            gui_render, gui_path, verify_reopen=True,
        )
        assert ezdxf.readfile(actual_path).audit().errors == []
        assert ezdxf.readfile(gui_path).audit().errors == []
        assert api.verify_saved_part_render_data_dxf(
            factory_render, gui_path,
        ).ok
        assert api.verify_saved_part_render_data_dxf(
            gui_render, actual_path,
        ).ok
        if key == UPPER and confirmed_features:
            circles = (
                entity for entity in ezdxf.readfile(gui_path).modelspace()
                if entity.dxftype() == "CIRCLE"
                and entity.dxf.layer == "CUTTING"
            )
            assert any(
                abs(float(circle.dxf.radius) - 6.875) < 1e-6
                for circle in circles
            )
