# DM1 #51 Execution Journal

## 身分與來源

- task id: `DIVIDER-FW-DEEP-MODULE-V1`
- 工單: `#51 / DM1`
- repository: `looaeedr/whd`
- branch: `work/dm1-divider-physical-contract`
- execution base: `cleanup/2d-3d-sync@11192e3ac47251e99fe1d2760031dada96fde227`
- `[當前角色：總控審查]`

## 完整實際呼叫鏈

DM1 追蹤的 Divider physical geometry chain 已補齊：

`Cabinet Family`
→ `ae_engine/cabinet_types/receiving.py`
→ `Fold Contract`
→ `ae_engine/cabinet_types/policy.py`
→ `Divider Physical Part`
→ `ae_engine/door_dividers.py::BoxBodyDividerPart`
→ `Manufacturing Resolve`
→ `ae_engine/manufacturing_api.py`
→ `fold_designer_bridge._phase6_resolve_manufacturing_geometry()`
→ canonical `resolved.part(divider_key).render_data`
→ `2D`：`fold_designer_bridge._phase6_query_final_render_data()`
→ `single-part 3D`：`fold_designer_bridge._phase6_render_true_cutting_mesh()`
→ `Assembly 3D`：`fold_designer_bridge._phase6_query_assembly_render_data()`
→ `DXF`：`ae_engine.manufacturing_api.save_resolved_manufacturing_geometry_dxf()`
→ `Save`：`fold_designer_bridge._phase6_build_project_snapshot()` → `phase6_project_file.write_project()`
→ `Reload`：`gui.BoxCalculatorGUI.load_phase6_project(..., open_designer=True)`
→ 再次 `_phase6_resolve_manufacturing_geometry()`。

### 呼叫鏈證據

歷史 acceptance commit `d2e7cb5a38c69e0b414d1e337f6d971c523555a8` 的 `tests/test_issue48_final_geometry_sync.py` 曾以真 GUI / 真 DXF / 真 Save-Reload 路徑逐段驗證：

1. canonical manufacturing solve 取得 Divider final material；
2. 2D active-sheet 讀同一 material；
3. single-part 3D 消費同一 material；
4. assembly 3D 收到同一 resolved Divider render data；
5. DXF CUTTING outer contour 與 canonical final material 相同，且 CUTTING circles 為 6；
6. project snapshot 寫檔後由 main GUI 真實 reload，再 solve 得到相同 material 與 placement evidence。

該 acceptance 測試後來在目前 branch 歷史中被移除；但 `d2e7cb5... → 4c234e4...` compare 顯示 `fold_designer_bridge.py`、`ae_engine/manufacturing_api.py`、`gui.py`、`phase6_project_file.py` 均不在變更檔案清單，因此上述 production 呼叫鏈在這段歷史中沒有被改寫。測試檔被移除不等於 production chain 被移除。

## 目前 raw segment seam

Receiving family contract 仍以 `frame_width_segment_index=1` 表示 18/FW/106/17 中的 FW segment；`policy.py` 驗證並重發；`BoxBodyDividerPart` 再保存該 implementation identity。這代表 downstream 若直接理解 raw segment index，就會把 cabinet-family fold topology 洩漏到 sink。

DM1 的目標邊界因此是：resolved Divider 必須提供一個 semantic physical geometry contract，讓 Manufacturing / Assembly / 2D / 3D / DXF / Save-Reload 消費 physical meaning，而不是自己理解 family name、magic FW 或 raw segment index。

## Phase6 Preflight

### changed-file hard gate

- run_id: `34223017421`
- head_sha: `3c9f04164c07259348766f0a39e377a846223490`
- changed files declared:
  - `tests/test_dm1_divider_physical_contract.py`
  - `.github/workflows/dm1-red.yml`
- terminal: `completed / success`

### final RED head Preflight

- run_id: `34223445675`
- head_sha: `4c234e4c726895efb488051f18628ceed77625ec`
- job_id: `102051763622`
- terminal: `completed / success`

## RED evidence

### INVALID / REVOKED — harness failure

- run_id: `34223151897`
- head_sha: `c62bd29daf97f7a3a91b6f912b13f16a35d909d0`
- job_id: `102050798345`
- classification: `INVALID_HARNESS / REVOKED`
- reason: pytest collection stopped at `ModuleNotFoundError: No module named 'ezdxf'` before any requirement assertion.
- action: added `ezdxf` to focused workflow dependencies and reran only unresolved RED scope.

此 run 永久不得計入 requirement RED / Combined Acceptance。

### FINAL VALID REQUIREMENT RED

- run_id: `34223445690`
- head_sha: `4c234e4c726895efb488051f18628ceed77625ec`
- job_id: `102051763633`
- terminal: `completed / failure`
- harness: dependencies installed; pytest collection succeeded; all target tests executed.
- result: `4 failed in 1.18s`

Failing guards:

1. `test_dm1_resolved_divider_contract_expresses_physical_geometry_boundary`
2. `test_dm1_sink_contract_does_not_leak_raw_segment_identity`
3. `test_dm1_fw_face_is_semantic_and_tracks_live_fw_without_magic_29`
4. `test_dm1_family_fold_topology_change_keeps_same_sink_contract`

共同 requirement failure：實際 `BoxBodyDividerPart` 尚無 `physical_geometry_contract`，所以四顆測試都在目標 architecture assertion 取得 `None`。這是需求 RED，不是 runner / collection failure。

第 4 顆另外把 family fold topology 從 4 segments 改成 5 segments，並把 FW implementation identity 從 index `1` 移到 `2`；sink-facing expectation 完全不改，專門鎖住「family topology 改變不得迫使 sink interface 改變」。

## RED contract 要求

目標 sink-facing contract 至少表達：

- `core_physical_segment`
- `fw_physical_face`
- `placement_datum`
- `final_material`
- `relief_evidence`

且不得要求 sink 理解：

- `frame_width_segment_index`
- `core_segment_index`
- cabinet family name 作為物理判斷條件
- magic FW `29`

live FW 以 `29 → 37` RED 驗證；fold topology 以 `4 segments/index 1 → 5 segments/index 2` RED 驗證。

## Production drift audit

`11192e3ac47251e99fe1d2760031dada96fde227 → 4c234e4c726895efb488051f18628ceed77625ec` compare：

只新增／修改 DM1 workflow、scratch evidence、checkpoint/journal 與 `tests/test_dm1_divider_physical_contract.py`；**沒有任何 production file 差異**。

因此：

- DM1 沒有偷做 GREEN；
- #47–#50 的 production code 沒被 #51 改動；
- 既有 acceptance evidence 沒被本工單的 production drift 破壞。

## DM1 QA 結論

- 完整 actual call chain：PASS
- changed-file Preflight：PASS
- raw-index / magic-FW / family-name leak guard：VALID RED
- semantic physical contract required fields guard：VALID RED
- family topology mutation / stable sink interface guard：VALID RED
- invalid harness provenance：已撤銷並保留
- production unchanged：PASS
- durable checkpoint/journal：PASS
- DM5 AI Library / Skill 正式回寫：依工單邊界延後，DM1 不偷跑

`[總控審查：ACCEPT DM1 / #51]`

下一個合法施工階段是 DM2 / GREEN implementation；DM1 本身不再修改 production。
