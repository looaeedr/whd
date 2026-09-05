# Box Body / EndCap Collision Relief Verification

## Commands

- `python -m pytest -q tests\test_assembly_collision.py tests\test_assembly_collision_integration.py tests\test_phase6_final_scene_view_ownership.py tests\test_endcap_resolved_geometry_ownership.py`
- `python -m py_compile ae_engine\assembly_collision.py ae_engine\contracts.py ae_engine\manufacturing_api.py`
- `python -m pytest -q tests\test_assembly_collision.py tests\test_assembly_collision_integration.py tests\test_endcap_resolved_geometry_ownership.py tests\test_phase6_final_scene_view_ownership.py tests\test_phase6_baseline_operation_alignment.py`
- `python -m pytest -q tests\test_phase6_baseline_operation_alignment.py tests\test_phase6_linked_fold_chain_and_parts.py tests\test_corner_semantics.py tests\test_manufacturing_api.py`

## Result

- Focused assembly/manufacturing/renderer ownership verification passed: 36 passed.
- `py_compile` passed with no output.
- Expanded local regression slice passed for the focused baseline command: 43 passed.
- Broader legacy slice did not complete green in this checkout: 60 passed, 9 skipped, 5 failed.

## Broader Slice Failures

The failing broader tests were outside the new assembly relief surface:

- `tests/test_phase6_linked_fold_chain_and_parts.py` expects `/mnt/data/自訂.p6fold`, which is not present in this Windows checkout.
- `tests/test_manufacturing_api.py::test_generate_part_endcap_baseline_and_tail_flag` creates a placeholder text file where the current path reads a real DXF through `ezdxf`.
- `tests/test_manufacturing_api.py::test_endcap_formula_contract_preserves_full_gui_parameters` expects the legacy formula exporter monkeypatch to receive parameters, while the current manufacturing path resolves through final scene render data.
- `tests/test_manufacturing_api.py::test_generate_part_supports_indicator_box` has no configured indicator shared baseline resource in this checkout.

## Scope

The verified implementation covers the first Box Body / EndCap slice only:

- Box Body material is retained.
- EndCap/Tail material is the cut owner.
- Collision is detected against resolved material polygons.
- Relief is projected back into EndCap 2D CUTTING.
- The EndCap render data is rebuilt and rechecked for remaining interference.
- GUI and final scene renderer do not call the assembly solver directly.

This is a 2.5D Shapely footprint solver, not a full CAD-kernel 3D solid solver.
