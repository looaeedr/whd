# DM1 #51 Execution Journal

## 身分與來源

- task id: `DIVIDER-FW-DEEP-MODULE-V1`
- 工單: `#51 / DM1`
- repository: `looaeedr/whd`
- branch: `work/dm1-divider-physical-contract`
- execution base: `cleanup/2d-3d-sync@11192e3ac47251e99fe1d2760031dada96fde227`
- `[當前角色：DM1 / #51 實作者]`

## 呼叫鏈追蹤

已確認 Divider FW segment identity 目前跨越下列層級：

`ae_engine/cabinet_types/receiving.py`
→ `ae_engine/cabinet_types/policy.py`
→ `ae_engine/door_dividers.py`
→ `ae_engine/manufacturing_api.py`
→ assembly/render data
→ `fold_designer_bridge.py`

目前 Receiving family contract 以 `frame_width_segment_index=1` 表示 18/FW/106/17 的 FW segment；policy 驗證並重發該 index；`BoxBodyDividerPart` 再把它保存成欄位。這使 sink 仍可能知道 fold-chain index 才能理解 FW physical face，正是 DM1 要封住的 seam。

## Preflight

有效 changed-file Preflight：

- run_id: `34223017421`
- head_sha: `3c9f04164c07259348766f0a39e377a846223490`
- changed files declared:
  - `tests/test_dm1_divider_physical_contract.py`
  - `.github/workflows/dm1-red.yml`
- terminal: `completed / success`

最終 RED harness head 的 Preflight：

- run_id: `34223265181`
- head_sha: `e127826c94dec4469b6f9e2633d7b4b8e906ef77`
- terminal: `completed / success`

## RED evidence

### INVALID / REVOKED — harness failure

- run_id: `34223151897`
- head_sha: `c62bd29daf97f7a3a91b6f912b13f16a35d909d0`
- job_id: `102050798345`
- classification: `INVALID_HARNESS / REVOKED`
- reason: pytest collection stopped at `ModuleNotFoundError: No module named 'ezdxf'` before any requirement assertion.
- action: added `ezdxf` to focused workflow dependencies and reran only unresolved RED scope.

此 run 不得計入 requirement RED / Combined Acceptance。

### VALID REQUIREMENT RED

- run_id: `34223265187`
- head_sha: `e127826c94dec4469b6f9e2633d7b4b8e906ef77`
- job_id: `102051168592`
- terminal: `completed / failure`
- harness: dependency install success; pytest collection success; target tests executed.
- result: `3 failed in 1.13s`

Failing tests:

1. `test_dm1_resolved_divider_contract_expresses_physical_geometry_boundary`
2. `test_dm1_sink_contract_does_not_leak_raw_segment_identity`
3. `test_dm1_fw_face_is_semantic_and_tracks_live_fw_without_magic_29`

共同 requirement failure：實際 `BoxBodyDividerPart` 沒有 `physical_geometry_contract`，因此在 `_physical_contract()` 的目標 assertion 得到 `None`。這證明目前尚未有單一 semantic Divider physical contract 可供 sinks 消費。

## RED contract 要求

目標 sink-facing contract 必須至少能表達：

- `core_physical_segment`
- `fw_physical_face`
- `placement_datum`
- `final_material`
- `relief_evidence`

且 sink-facing contract 不得暴露：

- `frame_width_segment_index`
- `core_segment_index`
- cabinet family name 作為物理判斷條件
- magic FW `29`

live FW 已在 RED 中以 `29 → 37` 驗證，目標契約必須跟隨產品 FW，而不是硬編碼 29 或 segment index。

## 工作狀態

- production code: 尚未修改。
- valid RED: 已取得。
- first harness failure: 已撤銷並保留 provenance。
- #47–#50 acceptance evidence: 未修改、未宣告失效。
- DM5 AI Library / Skill 正式回寫: 依 #51 scope 延後，不在 DM1 偷跑。

## 下一續跑點

1. `[轉移至：總控審查]`
2. `[當前角色：總控審查]`
3. 反讀 Issue #51、RED test、focused workflow、valid/invalid run logs、checkpoint/journal。
4. 若 RED 三類架構護欄覆蓋不足，先補 RED，不改 production。
5. DM1 僅在 Issue #51 acceptance 全部有 durable evidence 後才可關票／轉 DM2。
