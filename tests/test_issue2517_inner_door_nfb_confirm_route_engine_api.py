"""#2517 Receiving direct inner Door NFB Confirm All routes through public Engine."""
from __future__ import annotations

from copy import deepcopy
import inspect

import pytest

import ae_engine
from ae_engine import manufacturing_api as api
from ae_engine.receiving_nfb_csv_committed_config import (
    receiving_inner_door_nfb_confirm_required as owner,
)
from gui_modules.application.receiving_inner_door_hole_editor import (
    open_inner_door_hole_editor,
)
from tests.test_issue1500_receiving_candidate_main_save import (
    _source_with_saved_version,
)


def _source():
    _, staged, part_key, _ = _source_with_saved_version()
    return staged, part_key, staged["features"][part_key]


def test_public_engine_query_is_shared_with_package_and_is_read_only():
    staged, part_key, real_holes = _source()
    previous = deepcopy((staged, real_holes))
    assert ae_engine.receiving_inner_door_nfb_confirm_required is (
        api.receiving_inner_door_nfb_confirm_required
    )
    assert api.receiving_inner_door_nfb_confirm_required(staged, real_holes)
    assert owner(staged, real_holes)
    assert (staged, real_holes) == previous
    assert api.receiving_inner_door_nfb_confirm_required(None, real_holes) is False
    assert api.receiving_inner_door_nfb_confirm_required(staged, ()) is False


def test_no_csv_features_preserves_native_hole_confirm_route():
    staged, _, real_holes = _source()
    native = [deepcopy(real_holes[0])]
    # The candidate is physically valid, but an ordinary native operation
    # cannot become a submitted CSV source unless it carries that provenance.
    from dataclasses import replace
    native[0] = replace(native[0], source_type="MANUAL")
    initial = deepcopy((staged, native))
    assert api.receiving_inner_door_nfb_confirm_required(staged, native) is False
    assert (staged, native) == initial


@pytest.mark.parametrize("bad", [False, True, 0, "not-a-config", [], object()])
def test_invalid_staged_source_fails_closed_before_any_gui_write(bad):
    _, _, holes = _source()
    with pytest.raises(ValueError, match="STAGED_SOURCE_INVALID"):
        api.receiving_inner_door_nfb_confirm_required(bad, holes)


@pytest.mark.parametrize("bad", [None, "NFB_CSV_SOURCE", 1, True, object()])
def test_invalid_feature_collection_cannot_hide_source_or_commit(bad):
    staged, _, _ = _source()
    with pytest.raises(ValueError, match="FEATURES_INVALID"):
        api.receiving_inner_door_nfb_confirm_required(staged, bad)


def test_csv_shaped_but_invalid_feature_remains_on_strict_engine_commit_path():
    staged, part_key, _ = _source()
    class Spoofed:
        source_type = "NFB_CSV_SOURCE"

    assert api.receiving_inner_door_nfb_confirm_required(
        staged, [Spoofed()],
    ) is True
    with pytest.raises(ValueError):
        api.prepare_receiving_inner_door_physical_confirm(
            staged, part_key, [Spoofed()],
        )


def test_direct_gui_and_quantity_precommit_share_one_engine_source_owner():
    direct = inspect.getsource(open_inner_door_hole_editor)
    assert "manufacturing_api.receiving_inner_door_nfb_confirm_required(" in direct
    assert '"NFB_CSV_SOURCE"' not in direct
    assert "manufacturing_api.prepare_receiving_inner_door_physical_confirm(" in direct
    assert "manufacturing_api.commit_receiving_quantity_inner_door_confirm(" in direct
    source = inspect.getsource(api.preview_quantity_inner_door_confirm)
    # Facade forwards to the original Engine owner, where the same routing
    # decision is used before Quantity NFB provenance verification.
    import ae_engine.receiving_nfb_csv_committed_config as original
    assert "receiving_inner_door_nfb_confirm_required(config, features)" in (
        inspect.getsource(original.preview_quantity_inner_door_confirm)
    )
    assert "from gui_modules" not in inspect.getsource(original)
