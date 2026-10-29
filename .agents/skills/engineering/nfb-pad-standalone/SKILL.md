---
name: nfb-pad-standalone
description: NFB PAD V5 source-only standalone draft utility boundaries
whd_doc_role: CURRENT
whd_contract: nfb-pad-standalone
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Standalone NFB PAD preview safety

- The only numeric source is the existing per-brand NFB V5 CSV; never infer missing measurements or model-name dimensions.
- Reuse `ae_engine.receiving_nfb_pad_generator.generate_nfb_pad_patterns` and one common tooling JSON, never fork the formulas for an independent UI.
- Each physical tier has its own deepest NFB reference, not the brand max and not the whole project's max.
- UI 2D and 3D schematic are preview only: no world X/Y, real source Base plate, contact, manufacturing CHECK/Q or NC certification.
- Draft exports must carry NOT FOR MANUFACTURING conspicuously in the DXF and receipt. Never emit production `CUTTING`/`BEND` layers from this entry point.
- Update dedicated tests and `docs/manufacturing/nfb-pad-standalone-tool-20261028.md` together. All changes go to localX staging first; only user's explicit /推推 authorizes formal X.

- Portable ZIP is assembled from exact source files at build time via `tools/build_standalone_nfb_pad.py`; never check in cloned geometry implementations. The extracted archive needs no WHD GUI/config.ini but still needs Python 3.11+ and optional ezdxf for draft export.
