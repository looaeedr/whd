# Issue #119 Latest-Target Replay State

- owning_issue: `#119`
- production_target: `cleanup/2d-3d-sync`
- replay_base: `eede532b9fe61052cf4411ecf5063e0374165fe8`
- work_branch: `fix/issue119-replay-latest-20260912-r1`
- role: `QA`
- role_transfer: `[轉移至：QA]`
- accepted_tested_head: `de31d6709c3bab748b3cc3111b0c57bef1a671b1`
- integration: `PENDING HUMAN GATE; do not merge without explicit 合`

## Preflight / recovery

- First latest-target preflight run `34674548201` fail-closed because the evidence manifest omitted `release_required_artifacts.json`; production/test remained untouched.
- The missing reference was added as evidence and the same gate was rerun.
- Second preflight run `34674584890 @ 2302be682be0aeb4bf1410f545e579d344bc25fb`: **SUCCESS**; changed-file preflight and production/test untouched guard PASS.

## TDD RED on latest target

Run `34674665642 @ b65e37b24d407c184827390b67a64c9932f79506` deliberately executed regression tests before production changes.

- Durable knowledge: **2 FAIL**.
- Real Tk/Xvfb Issue119 UI: **5 FAIL**.
- Exact live failures: Corner Data left panel stayed managed after normal-part selection; first Vault→Receiving switch did not expose current BoxBody children; refresh-owner count was 0 instead of 1; operator-info weight remained normal; real `door` preview fit ratio was **0.932**.
- Production diff guard versus replay base: PASS / zero production changes.

## Minimal replay fix

Accepted production commit: `de31d6709c3bab748b3cc3111b0c57bef1a671b1` (`fix: replay Issue119 Corner Data lifecycle on latest target`).

The replay changes only the approved view seams:

1. selecting a formal part symmetrically removes the Corner Data left panel together with its canvas/info view;
2. visible Corner Data refreshes exactly once after the authoritative family/topology transaction commits and rereads post-commit `available_parts`;
3. operator-info base font is 11pt bold;
4. Corner Data uses its dedicated compact viewport (`top_gutter=64.0`);
5. duplicate finished-dimension summary is removed from the Corner Data canvas;
6. related durable rules are written to the Corner Data Skill and AI pitfall library.

No manufacturing geometry, DXF authority, physical-part identity, persistence schema, or formula authority was added or changed.

## Focused GREEN

Apply/focused run `34674784520`:

- Durable knowledge: **2 PASS**.
- Real Tk/Xvfb Issue119 UI: **5 PASS**.
- Real `door` preview fit ratio: **1.064**.
- The accepted replay commit pushed by the run is `de31d670...`.

## Final Part / DXF / Persistence Acceptance

Final run `34674868177`, job `103502804300`: **completed / success**.

The workflow trigger was QA-only; the job explicitly checked out exact tested head `de31d6709c3bab748b3cc3111b0c57bef1a671b1` and locked replay base `eede532b...`.

Results:

- Issue119 durable knowledge: **2 PASS / 0 FAIL**.
- Headless manufacturing / DXF / persistence matrix: **49 PASS / 10 SKIP / 0 FAIL**.
- Xvfb Corner Data + Receiving matrix: **14 PASS / 0 FAIL**.
- Real `door` preview fit: **1.064**.
- `config.ini` SHA256 before and after: `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67` — unchanged.
- `git diff --exit-code -- config.ini 基準檔`: PASS.
- final `git diff --exit-code`: PASS.
- final `git status --porcelain`: clean.
- tested HEAD remained exactly `de31d670...`.

Tk callback and missing-CJK-glyph warnings were observed, but the acceptance suites had zero failures.

## Temporary workflow cleanup

After terminal GREEN, all four replay-only workflows were removed from the work branch:

- `.github/workflows/issue119-r1-preflight.yml`
- `.github/workflows/issue119-r1-red.yml`
- `.github/workflows/issue119-r1-apply.yml`
- `.github/workflows/issue119-r1-final.yml`

Cleanup commits are QA-only. Final drift audit must prove tested-head → cleaned-head has zero production/test drift beyond this state document and workflow cleanup.

## Remaining gate

1. remote reread durable Skill / AI markers;
2. tested-head → cleaned-head production/test drift audit;
3. reread current `cleanup/2d-3d-sync` and verify target ancestry/drift;
4. post terminal evidence back to #119;
5. production integration remains human-owned and must not occur without explicit `合`.
