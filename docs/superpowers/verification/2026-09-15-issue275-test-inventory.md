---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# WHD TEST Inventory — #275 / T0

- Exact tested head: `f688d428bc5a8c2d176867079d455e879c88a06c`
- QA run: `34978576155` — SUCCESS
- Full inventory: `2136` nodes; Headless `2136` / Xvfb `2136`
- Full machine-readable inventory is stored as compressed UTF-8 CSV; manifest records the uncompressed/compressed SHA256 and run/artifact provenance.

## Lane counts
- `architecture`: 8
- `dxf`: 22
- `geometry`: 301
- `governance`: 183
- `persistence`: 25
- `projection`: 85
- `regression`: 1412
- `ui`: 100

## Classification counts
- `INHERITED_BASELINE_REQUIRES_SEPARATE_FIX`: 26
- `KEEP_CURRENT_CONTRACT`: 1826
- `MOVE_TO_GOVERNANCE_LANE`: 183
- `MOVE_TO_UI_LANE`: 100
- `REWRITE_SUPERSEDED_CONTRACT`: 1

## Confirmed first cleanup candidates
- `tests/test_phase6_semantic_doc_status.py::test_current_overlay_docs_point_to_v3_standard_plus_semantic_delta` — `REWRITE_SUPERSEDED_CONTRACT`; historically inherited red, but current structured metadata authority supersedes the old literal `CURRENT` contract.
- `tests/test_issue76_box_body_subtabs_2d_3d.py::test_designer_box_body_stays_one_top_level_part_but_has_switchable_physical_subtabs` — `INHERITED_BASELINE_REQUIRES_SEPARATE_FIX`; keep behavior contract, later remove unnecessary Tk implementation coupling if current authority permits.
- `tests/test_issue206_gui_modularization_characterization.py` — keep for now; review each characterization case for promotion to durable behavior/architecture contract or retirement if migration-only and replaced.
- `tests/test_issue209_part_panel_projection.py` — keep current physical-part projection contract; later rename/rehome away from issue-number taxonomy.
- `tests/test_issue210_project_actions_move_contract.py` — keep current module-ownership/no-reverse-dependency contract; later rename/rehome.
- `tests/test_issue211_renderer_dependency_gate.py` — keep current renderer dependency/ownership contract; later separate behavior from source-location structure checks where appropriate.
- `tests/test_box_body_single_source_t3.py` — keep authoritative render/projection/no-caller-rebuild behavior; reconcile logical vs physical identity expectations in its owning cleanup task.

## T0 conclusions
- `tests/knowledge/**` and `tests/process/**`: governance lane candidates; they remain valid tests and are not deleted.
- Tk/DISPLAY-dependent nodes: UI lane candidates; current inventory detects 100 nodes from actual headless `skipif(DISPLAY/Tk/Xvfb)` state and explicit display markers.
- Historical inherited-red evidence covers 27 exact nodeids. T0 does not convert red into deletion permission.
- The semantic-doc node is the one current-authority override: its old string-based contract is superseded by `WHD_DOC_META_V1` / Canonical Authority Map, so it is classified for rewrite rather than preserved as an inherited-red contract.

## Safety / invariants
- Production source changes: **0**.
- Geometry / DXF / schema behavior changes: **0**.
- `config.ini` / DXF protected manifest: **PASS** before/after collection.
- Test deletion / assertion weakening: **0**.
- Historical #212 evidence was used only as provenance for 27 known inherited nodeids; #212 was not executed or monitored by T0.
