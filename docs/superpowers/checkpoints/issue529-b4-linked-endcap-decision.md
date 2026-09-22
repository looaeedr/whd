# Issue #529 / B4 — Linked Endcap Boundary Reconsideration

- Master: #520
- Parent accepted HEAD: `f06309c0741a4a4ab22ec43cfad4405cc1264ec2`
- Tested HEAD: `4d1618937dd342b67a82c45b1f29feca86661a18`
- Formal Deletion-Test RUN: `35793499633`
- Artifact: `10722084894`

## Decision

`KEEP_COMPATIBILITY`

This is a fresh Phase 6 v1.4 revalidation of the prior #481 boundary, not an automatic inheritance of the old KEEP result.

## Evidence

- Current bridge seam span: **61 LOC**
- Derivation remains `phase6_fold_profiles.build_linked_endcap_xy_profiles`
- Variant K: full-app dependency returns; caller regains workspace mutation/live-effect ordering
- Variant E: forbidden imports = 0; full-app dependency = false; **old effect body removed = false**
- Headless: **55 passed / 5 skipped**
- Xvfb linked/live workspace path: **10 passed / 24 deselected**
- `JOIN_DERIVED_PART_PLAN=false`
- `DEEPEN_FOLD_PROFILES=false`
- production change required: **false**
- bridge symbols removed: **0**

## Ownership

- Fold derivation: `phase6_fold_profiles`
- Workspace mutation authority: remains outside Fold Profile owner
- Bridge: retains workspace/live-editor compatibility effects
- Derived physical-part plan: remains separate from Linked EndCap canonical profile refresh

Stage B remains mandatory and continues with #530/B5.
