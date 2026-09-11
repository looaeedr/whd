# Issue #116 — UI設計與去AI味 Governance Evidence

## Owning Issue / Authority

- Owning Issue: #116 `接上 UI設計與去AI味 Registry / README / AI08 / release governance`
- Approved RED IDs: R4, R5, R6
- Parent T1 / #115: CLOSED / ACCEPTED at `d3f3ed0c5671f9ef3e6eec84d9c2ec33a84056f7`.
- Requirement RED: run `34604972890 @ 2eeab44083c9445f1a0f99939f774053917ce465` → `0 PASS / 6 FAIL`; R4–R6 user-approved.
- Work branch: `feat/issue116-ui-design-governance-20260911` from exact #115 final head.
- Production `cleanup/2d-3d-sync` remains untouched without explicit user `合`.

## Read Evidence

READ_SKILL: UI設計與去AI味
READ_SKILL: 寫技能
READ_SKILL: Python測試實務
READ_SKILL: phase6-release-packaging
READ_SKILL: monitoring-remote-qa
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: release_required_artifacts.json

## T2 scope

T2 owns R4–R6 only:

1. machine routing / README discovery;
2. AI08 durable writeback including anti-global-replace / per-component / Action Color / monospace / elevation / text-scale / visual-capability rules;
3. release mandatory artifacts and contract integration.

T1 Skill body remained accepted input and was not rewritten.

## Bootstrap Preflight

- run `34608767314 @ c0c7cda738b64223a40b7b0a4f189760fd5e0686` → SUCCESS.
- Required Skills: `寫技能`, `phase6-release-packaging`, `monitoring-remote-qa` → PASS.
- Required references: AI06, AI08, `release_required_artifacts.json` → PASS.
- `config.ini` before/after SHA256 = `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`.

## Formal T2 RED

- run `34608956015 @ cc8506317891a948a68e8756d9028d0475397e0e` → terminal FAILURE after Preflight PASS.
- Result: `8 passed / 3 failed`.
- T1 R1–R3 guards all remained GREEN.
- R4 failed because `ui-design-de-ai` Registry route / README integration were absent.
- R5 failed because fifth-batch AI08 durable section was absent.
- R6 failed because release manifest did not require the new Skill / contract.
- `config.ini` invariant PASS.

## Governance implementation

- Registry route `ui-design-de-ai` added with intent keywords including `UI設計`, `UI`, `UX`, `去AI味`, `AI味`, `AI slop`, `不像AI`, `介面設計`, `介面重整`, `視覺層級`, `layout`, `typography`, `UI audit`, `frontend design`.
- Registry file glob is limited to `.agents/skills/engineering/UI設計與去AI味/**`; no broad `gui.py` glob.
- Engineering README now links canonical `UI設計與去AI味` path.
- AI08 contains fifth-batch durable UI rules: external sources are input only; Tkinter/ttk boundary; functionality > aesthetics; no global style replace; explicit `逐元件` rewrite; Action Color; monospace width/clipping guards; foreground elevation; text-scale `1.0/1.2/1.4`; no fake visual acceptance.
- `release_required_artifacts.json` now requires `.agents/skills/engineering/UI設計與去AI味/SKILL.md` and `tests/test_ui_design_de_ai_skill_contract.py`.

## GREEN and correction loop

- first GREEN attempt run `34610224381 @ 08064329dc7cf4b4616caf6043d985276a41f996` → `10 passed / 1 failed`.
- sole failure: AI08 durable wording did not contain the explicit marker `逐元件`; implementation was corrected, contract was not weakened.
- run `34610387667 @ 3aed1b4f021647405f258cffe5bc518cc0337a86` → SUCCESS, `11 passed / 0 failed`.

## UI task-intent route proof / tested head

- tested head: `e60c8437cb816dc2a54941742b9063e22b709d23`.
- final proof run `34610530609 @ e60c8437cb816dc2a54941742b9063e22b709d23` → SUCCESS.
- generic task used for route proof: `把設定頁做介面重整，改善視覺層級、layout 與 typography，不改 callback、資料或工程功能`.
- route proof result: required Skill `UI設計與去AI味`; required references AI06 + AI08. The task did not name the Skill directly.
- formal R1–R6 contract: `11 passed / 0 failed`.
- `config.ini` before/after = canonical `980eab68d4a1732a5313b22329852dfc9691c83e4e2a64cccd18022afae4ee67`.
- `git diff --exit-code` PASS.

## Remote readback at tested head

- Registry blob `56acab1ce5c3aee9694daf5b5cbdc38aeb17028f` contains intent-scoped `ui-design-de-ai` route.
- Engineering README blob `f13da21b61510c865917b9a29df5eb04b5812700` contains canonical UI Skill entry.
- AI08 blob `66dd736c433ef4a7b6265a1c32cb57a9ca7bd0d5` contains fifth-batch durable rules including `逐元件`.
- Release manifest blob `8d4f9868f4c9f2a20177828e86f0032e54920bac` requires the Skill and contract test.

## Dispatch checkpoint

- Task: Fifth batch `UI設計與去AI味`
- Ticket: #116 / T2
- Current role: T2 Implementer preparing QA handoff
- Branch: `feat/issue116-ui-design-governance-20260911`
- Completed: branch-first, T2 Preflight, valid T2 RED, Registry/README/AI08/release integration, correction loop, R1–R6 GREEN, generic UI intent route proof, tested-head remote readback.
- Pending: temporary workflow/sentinel cleanup, 404 verification, tested-head→cleaned-head drift audit, final issue evidence/comment, QA ACCEPT.
- Failed/blocked: none.
- Verification runs: `34608767314`, `34608956015`, `34610224381`, `34610387667`, `34610530609`.

## Acceptance state

- R4/R5/R6: GREEN.
- UI task-intent Preflight route: GREEN.
- Durable governance remote readback: GREEN.
- Final T2 acceptance: PENDING cleanup/drift/QA review.
