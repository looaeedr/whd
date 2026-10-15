---
whd_doc_role: HISTORICAL
whd_contract: verification-provenance
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---
# #1796 GUI / 3D 效能完整性：2026-10-16 中途驗收 Checkpoint

**性質：部分驗收證據，不是整體結案／Windows 驗收／正式 X 發布。**

## Exact repository authority

- Repository: `looaeedr/whd`; integration target: GitHub `localX` only.
- Source after #1806 merge/readback: `8ba22bf0a49975724ed9f4017ca60a11eef1c22b`.
- Source owner: `.agents/skills/engineering/phase6-gui-performance-integrity/SKILL.md` (CURRENT).
- #1796 remains OPEN; #1794 precise derived-cache invalidation remains OPEN with prior GitHub mutation security-review blocker. This document does not bypass or waive that restriction.
- Formal X and Windows local `Z:\localX` were not modified or verified by this chain.

## Completed prerequisite issue evidence

| Issue | Scope | GitHub PR | Merge SHA | Product CI run |
|---|---|---|---|---|
| #1789 | Scheduler reentrant dirty | #1798 | `9392008abc447b021581aadd95652197fd68f896` | `38782997701` SUCCESS |
| #1790 | 3D Save fails closed | #1799 | `4346446c865af39d267f2b0210c2a81dfa880700` | `38785390411` SUCCESS |
| #1791 | Receiving Configure idle render coalescing | #1803 | `b6a346f410917abd07c146b03dacc68eb3335c0f` | `38794649230` SUCCESS |
| #1792 | Mandatory canonical GUI performance test selectors | #1800 | `ecd54d9d79a53eee280e06e8a96804e8c5737cdb` | `38788975027` SUCCESS |
| #1793 | 12-switch measured regression; no product rewrite | #1802 | `a997abfb66b571a34bab7eed991b6b5e498f1089` | `38791481958` SUCCESS |
| #1795 | Main GUI/3D real Tk anti-echo + UI scale | #1804 | `1798b4ecbdcece2ec8968706b35f9d435c699d40` | `38798376499` SUCCESS |

## #1796 actual partial acceptance, already merged

1. [PR #1805](https://github.com/looaeedr/whd/pull/1805) exact head `8f2d2a7eaa2e12695517686c15bf36dcf3b92bbf` → `localX` merge `84f7fe277abb9d87b2fa65297255c7703a39bfdd`. Product Regression [run 38810444511](https://github.com/looaeedr/whd/actions/runs/38810444511): Preflight, Shards 0/1/2 and Canonical ALL SUCCESS. Full-file canonical selector `tests/test_phase6_part_switch_performance.py` covers W/H/D/T **20 edits each**, final committed values, Scheduler calculation flush <= 1, same baseline DXF reread = 0, and five 3D OFF/ON switches with part navigation, OFF render = 0 and solve = 0. These are test-scoped assertions, not universal guarantees.
2. [PR #1806](https://github.com/looaeedr/whd/pull/1806) exact head `a7e9007234a61663900d40747bfbee361889be78` → merge `8ba22bf0a49975724ed9f4017ca60a11eef1c22b`. Product Regression [run 38811573830](https://github.com/looaeedr/whd/actions/runs/38811573830): all five jobs SUCCESS. Canonical manifest now selects actual Tk Main GUI Save As→Save→Open and connected 3D Designer Save As→committed host project; its sharding guard asserts both selectors and the existing full-file `tests/test_issue1500_real_nfb_dxf_lifecycle.py` DXF submit/copy/undo/reopen test.
3. Existing canonical `tests/test_manufacturing_mesh_reuse.py` compares geometry and complete manufacturing-result behavior; #1786 has its own completed equality/CI evidence. These do not substitute for final all-mode combined verification.

## Durable CI artifacts

- Run 38810444511: `whd-ci-shard-1` artifact ID `12008202895` (real Tk metrics and wall-time JUnit properties); `whd-canonical-complete-junit` artifact ID `12008661519`.
- Run 38811573830: `whd-ci-shard-1` artifact ID `12007984663`; `whd-canonical-complete-junit` artifact ID `12008354450`.
- Source/package identity: exact tested PR heads and merge SHAs above; worktree/patch hash and collection SHA must be captured if the release gate separately requires them. JUnit pass does not prove Windows GUI smoothness or measured speedup.

## Incomplete / not yet authorized claims

- `#1794` derived cache `changed_keys` and redundant physical-presence invalidation still open; prior review-blocked mutation remains unresolved. No current repair or GREEN for #1794.
- Combined all-mode Family/Assembly/Receiving stress and collision/scene/2D/3D/DXF parity across every requested interaction is not yet certified as one matrix; some existing per-suite tests are mandatory, but do not combine to a full end-to-end UAT claim.
- Windows `Z:\localX` fast-forward and real-machine 3D/Tk GUI UAT: `WINDOWS_LOCALX_SYNC_PENDING` / `WINDOWS_UAT_PENDING`.
- AI Library root-cause and prevention writeback: `AI_LIBRARY_WRITEBACK_PENDING` until a writable current target is verified. This checkpoint is not a substitute for that file.
- Process group/Xvfb/pytest orphan scan and timing tail/lab-vs-Windows comparison: pending distinct evidence.

## Next exact action

1. Once GitHub permits #1794 without bypassing the review, implement minimal scoped RED→GREEN geometry cache invalidation; keep immutable DXF source and SOURCE_UNVERIFIED fail-closed; exact head Product Regression and merge/readback.
2. Rebase/reconcile remaining #1796 acceptance on then-current `localX`, complete full GUI Family/Assembly/Receiving and Save/Export/DXF/Scene/Collision matrix, record wall-time distributions, executor/scene/render/DXF-read counters and source/collection hashes.
3. Have user update Windows `Z:\localX` and perform manual Windows GUI UAT; preserve independent SHA, screenshots/logs and outcome.
4. Complete AI Library lessons writeback and readback; close #1796 only after all evidence and prerequisite issue closure readback. Do **not** release X without current `/推推`.
