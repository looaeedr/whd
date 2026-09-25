---
whd_doc_role: REFERENCE
whd_contract: issue312-t8-cleanup-evidence
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# Issue 312 / T8 Cleanup Gate Evidence

Date: 2026-09-17 (Asia/Taipei)

## Preconditions

- Final acceptance evidence secured: **true**
- OPEN PR refs refreshed immediately before deletion: **true**
- OPEN PR count before deletion: **0**
- OPEN PR protected refs: `[]`
- Active T8 branch protected: `ci-sharding/issue312-t8-final-qualification-20260917`
- Production branch protected: `cleanup/2d-3d-sync`
- Cleanup scope was restricted to temporary `qa/*` refs from the completed #303 child chain; unrelated active chains such as #292 were excluded.

## Guard implementation

Because the chat connector did not expose a delete-ref action and the local runtime had no authenticated `gh`/git credential, T8 used a one-shot GitHub Actions workflow with `contents: write` and `pull-requests: read`.

The workflow re-read `issue312-t8.json`, required `evidence_secured=true`, `cleanup_authorized=true`, and `production_mutated=false`, refreshed OPEN PR head/base refs, then deleted only the exact approved candidate list. Any protected candidate or remaining ref would fail closed.

## Execution evidence

- Cleanup RUN: `35169210627`
- Cleanup RUN head: `0b2b1813580793ee514db85f0594bb09e609019d`
- Conclusion: **SUCCESS**
- Approved candidates: **15**
- Deleted now: **15**
- Deleted live PR refs: `[]`
- Production branch preserved: **yes**
- Active T8 branch preserved: **yes**

Deleted refs:

- `qa/issue304-t0-closing-verification-20260916`
- `qa/issue304-t0-closing-verification-fix-20260916`
- `qa/issue305-t1-closing-verification-20260916`
- `qa/issue305-t1-closing-verification-fix-20260916`
- `qa/issue305-t1-focused-green-20260916`
- `qa/issue305-t1-live-manifest-20260916`
- `qa/issue305-t1-red-20260916`
- `qa/issue306-t2-aggregate-cli-red2-20260916`
- `qa/issue306-t2-aggregate-cli-red-20260916`
- `qa/issue306-t2-closing-verification-20260916`
- `qa/issue306-t2-focused-green2-20260916`
- `qa/issue306-t2-focused-green-20260916`
- `qa/issue306-t2-parallel-acceptance2-20260916`
- `qa/issue306-t2-parallel-acceptance-20260916`
- `qa/issue306-t2-red-20260916`

## Fresh post-cleanup census

- `qa/issue304*`: **0**
- `qa/issue305*`: **0**
- `qa/issue306*`: **0**
- OPEN PR count after cleanup: **0**
- Production HEAD after cleanup: `8ccf1a9404a641ed892ab63e6f2c0e01ee80d6d9`
- Active T8 branch HEAD after cleanup run creation: `0b2b1813580793ee514db85f0594bb09e609019d`

## Final cleanup status

`CLEANUP_COMPLETE`
