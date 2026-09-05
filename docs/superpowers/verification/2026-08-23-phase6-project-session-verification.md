# Phase6 ProjectSession 專案交易所有權驗證報告

## 驗證範圍

本輪只收斂 Phase6 專案交易狀態，不變更 `.p6fold` schema、Factory Defaults、EndCap／CornerType／Fold Profile 製造幾何。

完整交易鏈：

```text
主 GUI canonical snapshot
        ↓
ProjectSession.committed
        ↓ begin_draft
3D 隔離 transaction
   ├─ 取消 / X → cancel_draft → committed 不變
   ├─ 確定 → 套回 main GUI → commit_draft(canonical main snapshot)
   └─ 全域 Save / Save As → main GUI → snapshot_for_save(committed)
```

`loaded_baseline` 只代表最近成功載入的原始 snapshot；後續 committed 修改不得反向改寫。`_runtime_project_path` 只屬 3D 執行期資訊，不持久化進 `.p6fold`。

## TDD／契約驗證

新增 `tests/test_phase6_project_session.py`，鎖定：

1. defensive deepcopy 與 Cancel isolation。
2. draft 尚未提交時 `snapshot_for_save()` 仍只回 committed。
3. Confirm／`commit_draft()` 後 committed 才更新。
4. Load 同時建立 project path、loaded baseline、committed，並清除舊 draft。
5. active draft 期間直接 `capture_committed()` 必須拒絕。

`tests/test_phase6_project_file.py` 新增 real-Tk integration，鎖定：

1. loaded baseline W=400，main committed recapture W=450 後 baseline 仍為 400。
2. 3D staged W=500 + Cancel → main／committed 都維持 400。
3. 3D staged W=500 + Confirm → main／committed 變成 500。
4. main-connected 3D staged W=500 + Save As → `.p6fold` 仍為 committed W=400。
5. 正式 snapshot 不得保存 `_runtime_project_path`。

既有 `test_3d_global_save_as_then_save_reuses_same_project_path` 另外驗證：目前正在看的已存在 committed 板件可保存成 `active_part` 導航 metadata；這個例外不會提交 staged 機械資料。

## 最終新鮮驗證

### Python 語法

```text
python -m py_compile phase6_project_session.py gui.py fold_designer_bridge.py \
  phase6_project_file.py tests/test_phase6_project_session.py tests/test_phase6_project_file.py
```

結果：`exit 0`。

### 聚焦交易／GUI 回歸

```text
xvfb-run -a python -m pytest \
  tests/test_phase6_project_session.py \
  tests/test_phase6_project_file.py \
  tests/test_corner_lock_visual_contract.py \
  tests/test_phase6_ui_state_regressions.py \
  tests/test_phase6_3d_retain_and_baseline.py -q
```

結果：`59 passed, 30 warnings`。

warnings 為 Linux 測試環境 DejaVu Sans 缺繁中文字形的 Tk `UserWarning`，不是功能失敗。

### 完整原始 suite

```text
xvfb-run -a python -m pytest -q
```

結果：`267 passed, 2 skipped, 4 failed, 65 warnings`。

4 個 failure 全部是既有測試硬編碼外部 fixture `/mnt/data/自訂.p6fold`，目前交付環境沒有該檔：

1. `test_uploaded_custom_project_proves_legacy_scene_was_not_using_saved_five_segment_chain`
2. `test_loading_uploaded_custom_project_does_not_reinflate_five_segments_to_legacy_nine`
3. `test_real_main_2d_result_uses_loaded_authoritative_box_fold_chain_width`
4. `test_real_delete_confirm_readd_linked_tail_confirm_roundtrip`

四項錯誤皆為 `FileNotFoundError: /mnt/data/自訂.p6fold`，與本輪 ProjectSession 修改前的已知環境限制相同。

### 明確排除缺件 fixture 的完整 suite

對上述 4 個 node id 使用 `--deselect` 後重新執行完整 suite。

結果：`267 passed, 2 skipped, 4 deselected, 65 warnings`，**0 failure**。

## 實作審查

- `ProjectSession` 是純 Python deep module，不 import Tk、Bridge、AE 或 renderer。
- session 只擁有 transaction lifecycle 與 snapshot 邊界，不同步每個 Tk 欄位，因此沒有形成新的 live-state mirror。
- main-connected Bridge 只透過 `on_project_save` callback 委派；standalone fallback 保留。
- `active_part` 只作導航 metadata，且 main save 只接受 committed `existing_parts` 中已存在的 hint。
- `capture_committed()` 在 active draft 時設 guard，caller 無法繞過 transaction。
- `.p6fold` schema 維持 `phase6-fold-project-v1`。

## config.ini

修改前 SHA256：

`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`

最終驗證前 SHA256：

`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`

本輪未修改 `config.ini`。

## 封包驗證

最終交付檔名共用 Asia/Taipei 時間戳 `20260823_115316`：

- `PHASE6_PROJECT_SESSION_FULL_20260823_115316.zip`
- `PHASE6_PROJECT_SESSION_UPDATE_20260823_115316.zip`

UPDATE 固定只含本輪 13 個修改／新增檔，且不得包含 `config.ini`。最終交付前需對重建後的兩個 ZIP 再執行 `python -m zipfile -t` 與 `ZipFile.testzip()`；交付訊息只引用最後一次重建後的驗證結果。
