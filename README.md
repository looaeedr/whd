# WHD — default branch tombstone

<!-- MAIN_DEFAULT_BRANCH_FAIL_CLOSED_V2 -->

This `main` branch is intentionally a **minimal fail-closed navigation surface**.

- CURRENT production / process / Skill / governance authority: `cleanup/2d-3d-sync`
- The previous full `main` tree is preserved at `archive/main-default-full-tree-20260930-c6aff6e9`.
- Do not use default-branch code search, files, Skills, tests, or docs as WHD CURRENT authority.
- Bind every WHD execution/read to the live `cleanup/2d-3d-sync` ref explicitly.

This branch does not mirror, synchronize, or validate parity with production. Its only purpose is to prevent omitted-ref/default-branch retrieval from reviving stale execution semantics.
