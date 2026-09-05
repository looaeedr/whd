# Assembly View Joint Debug Clean — Corrected Verification

## Root cause
- WRAP / Joint Registry development diagnostics were connected directly to the production combined assembly view.
- The operator view therefore gained a Joint selector, long Registry/preserve/relief/pre-post status text, and diagnostic overlay capability that did not exist in the last clean operator layout.
- The uploaded `金庫型.p6fold` contains four `LEGACY_MIGRATED` joints. They are assembly semantics, not extra physical parts and not operator drawing layers.
- The later report of「缺東缺西」was traced to the UPDATE package being built only as the narrow 20:45→21:11 delta instead of the required cumulative UPDATE from the canonical 2026-08-23 baseline.

## Correct fix boundary
- Production assembly view carries no Joint debug overlay and no selected debug Joint.
- Operator assembly diagnostics UI does not expose the newly-added Joint debug selector/status suffix.
- Joint / WRAP / collision diagnostics remain in canonical `ResolvedManufacturingGeometry` for registry/debug tooling.
- Single-part 3D remains on the canonical FinalScene path: Box Body / EndCaps / USER_ADDED-Joint participants read resolved assembly geometry; unrelated Door/Base Plate sheets query their own canonical manufacturing FinalScene instead of forcing an invalid whole-cabinet solve. This is retained because the single-part 3D gate fails without it.
- FULL remains complete. UPDATE is cumulative from `PHASE6_FW_LINK_BUGFIX_FULL_20260823_212355(3).zip`, always includes `個人AI檔案庫/**`, excludes `config.ini`, and excludes BACKUP/cache files.

## Required evidence
- `金庫型.p6fold` operator view matches the clean pre-Joint-debug layout while retaining the same physical assembly parts/geometry.
- INSERT / OVERLAY / INSERT_OVERLAY registry-driven Head/Tail, collision, zero-penetration, 2D/single-3D/assembly, and save/reload gates pass.
- Packaging policy tests prove unchanged `個人AI檔案庫/**` still enters UPDATE and `config.ini` never does.
- Both ZIPs must pass CRC, extract cleanly, and match source SHA256 before delivery.

## Fresh corrected gate (20260829_215535)
- non-GUI focused matrix: `145 passed`.
- Tk single-part 3D / cutting / return-to-2D: `1 passed` each in isolated Xvfb processes.
- registry GUI matrix: `3 passed` (INSERT / OVERLAY / INSERT_OVERLAY).
- latest layout contract: `11 passed`.
- uploaded `金庫型.p6fold` matches pre-Joint-debug 16:08 geometry/visibility: assembly parts identical; `mesh_triangles=1502`; `interference_segments=454`; no operator Joint debug widgets/layers.
- package policy gate is part of the focused matrix and locks cumulative baseline + full personal-AI tree + forbidden `config.ini`.
