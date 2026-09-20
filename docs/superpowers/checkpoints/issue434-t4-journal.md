# Issue #434 / T4 — Corner Data mounted into the shared-content host

## Authority
- Parent: #429
- Predecessor: #433 CLOSED/completed
- Exact T4 base: `bbd499786cbebc1b5e68ff032f2591cc308060cd`
- Branch: `refactor/issue434-t4-corner-data-shared-host-20260920`

## Knowledge Preflight
- RUN `35498340890`
- result: SUCCESS

## Ownership readback
Current production already uses:
- lazy `corner_data_panel = ttk.Frame(shared_content_host, ...)`;
- `_phase6_mount_shared_content(..., "corner_data")` as the mount owner;
- `Phase6CornerDataViewAdapter._selected_part_key` as the Corner Data selection owner;
- `_phase6_corner_data_selected_part_key` only as a compatibility mirror;
- authoritative workspace `available_parts` for part projection;
- authoritative render-data sinks for unfold projection.

T4 must not create a second panel, second selection store, legacy Notebook route, or independent window.

## Characterization strategy
Keep both production files byte-identical to predecessor:
- `fold_designer_bridge.py`
- `phase6_corner_data_view_adapter.py`

Run:
- new #434 host/mount/adapter identity tests;
- #94 view-only mode tests;
- #95 authoritative part-projection tests;
- #96 stable-selection lifecycle tests;
- #119 real Tk transition/refresh/readability/viewport tests.

If all gates are GREEN:
`T4_ALREADY_GREEN_AFTER_T1=1`; no production change is needed.

## Gates
```text
CORNER_DATA_HOST_IS_SHARED_HOST=true
SEPARATE_CORNER_DATA_REGION=0
CORNER_DATA_WIDGET_TREE_COUNT_WHEN_ACTIVE=1
CORNER_DATA_WIDGET_TREE_COUNT_WHEN_INACTIVE=0
CORNER_DATA_BEHAVIOR_DRIFT=0
CORNER_DATA_STATE_AUTHORITY_DUPLICATION=0
PRODUCTION_RUNTIME_EDIT=0
```

## State
```text
STATE=CHARACTERIZATION_PENDING
NEXT_ACTION=Run exact T4 Xvfb characterization with production byte-identical to predecessor.
```
