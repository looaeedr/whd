# Phase6 診斷快照最終驗證報告

## 驗證時間

- Asia/Taipei：2026-08-23 14:03:43 CST

## 本輪架構結果

- 新增 `phase6_diagnostics.py`，集中 diagnostic schema、JSON-safe、Scene／Material／FoldGuide 序列化、active snapshot 與 all-part Final Geometry diagnostics。
- `fold_designer_bridge.py` 保留 Designer state → context／payload/provider adapter、Project Snapshot reloadable state 與 Tk 檔案對話框。
- Bridge 舊 serializer 名稱改為 Diagnostics 函式的 direct re-export；沒有 wrapper／第二套 serializer。
- Diagnostics 不依賴 Tk、Bridge、ProjectSession、SettingsService，也不呼叫 manufacturing build/material reconstruction。
- Bridge 行數：4118 → 4009；新 Diagnostics module 191 行。行數不是目標，重點是 diagnostics knowledge 的 locality。

## TDD / ownership

- `tests/test_phase6_diagnostics_ownership.py`：**7 passed**。
- 第一個 RED：`ModuleNotFoundError: phase6_diagnostics`。
- 第二個 RED：Bridge serializer 尚非新 module 的同一 function object。
- GREEN 後確認：active snapshot、含洞 material、FoldGuide、all-part error isolation、UTF-8 JSON writer、Bridge direct re-export 全部通過。
- AST／source ownership guard：**OWNERSHIP_OK**。

## 完整回歸

### 原始完整 suite

`xvfb-run -a python -m pytest -q`

- **311 passed**
- **2 skipped**
- **4 failed**

4 個 failure 全部為既知外部 fixture `/mnt/data/自訂.p6fold` 不存在：

1. `test_uploaded_custom_project_proves_legacy_scene_was_not_using_saved_five_segment_chain`
2. `test_loading_uploaded_custom_project_does_not_reinflate_five_segments_to_legacy_nine`
3. `test_real_main_2d_result_uses_loaded_authoritative_box_fold_chain_width`
4. `test_real_delete_confirm_readd_linked_tail_confirm_roundtrip`

本輪沒有新增 failure。

### 明確排除既知 4 項後

- **311 passed**
- **2 skipped**
- **4 deselected**
- **0 failure**

## 語法與設定保護

- `python -m py_compile phase6_diagnostics.py fold_designer_bridge.py tests/test_phase6_diagnostics_ownership.py`：通過。
- `config.ini` 修改前 SHA256：`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`
- `config.ini` 修改後 SHA256：`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`
- 結論：`config.ini` 未修改。
