# Phase6 3D Designer 草稿工作區驗證報告

## 驗證範圍

本輪將 Fold Designer 內分散的板件生命週期狀態收斂到 `phase6_designer_workspace.py`，驗證重點不是單純檔案行數，而是確認 presence、active/selected、profile/feature stash、dirty、switching 與跨輸出 snapshot 已由同一 owner 管理。

## 所有權驗證

- `Phase6DesignerWorkspace` 為純 Python 模組，不依賴 Tk、AE、renderer、ProjectSession、SettingsService 或 FinalScene View。
- `available_parts / active_part_key / selected_part_key / _phase6_part_profiles / _phase6_part_features / _phase6_part_face_features / _phase6_workspace_dirty / _phase6_switching_part` 在真實 Designer 上只保留 compatibility property，不形成第二份 `__dict__` backing state。
- Bridge production method 不再直接 `append/remove` legacy `available_parts`、直接寫 `_phase6_part_profiles[...]`，也不直接切換 legacy dirty/switching flag。
- Project snapshot、Diagnostics、Scene query 與 FinalScene request 的 presence／active／profile／features 皆從同一 Designer Workspace owner 取得。

最終 AST ownership 檢查結果：`OWNERSHIP_OK`。

## TDD 與聚焦回歸

`tests/test_phase6_designer_workspace.py` 最終結果：

```text
11 passed
```

其中包含真 Tk ordering 契約：切換板件時必須先保存 outgoing draft，之後才讓 Workspace 開始切換 target。

## 完整測試

原始完整 suite：

```text
333 passed, 2 skipped, 4 failed
```

4 個 failure 全部是既知外部 fixture 缺件，皆因 `/mnt/data/自訂.p6fold` 不存在：

1. `test_uploaded_custom_project_proves_legacy_scene_was_not_using_saved_five_segment_chain`
2. `test_loading_uploaded_custom_project_does_not_reinflate_five_segments_to_legacy_nine`
3. `test_real_main_2d_result_uses_loaded_authoritative_box_fold_chain_width`
4. `test_real_delete_confirm_readd_linked_tail_confirm_roundtrip`

明確排除上述 4 個外部 fixture 後，完整可執行 suite：

```text
333 passed, 2 skipped, 4 deselected, 0 failure
```

## 語法與設定檔

- `py_compile`：通過。
- `config.ini` 未修改。
- `config.ini` SHA256：

```text
5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d
```

## 行為結論

- `box_body` 仍為 mandatory part。
- 刪除非箱身板件只改 presence，profile／feature stash 保留；重新加入可恢復。
- Home 清除 active/selected，但不清 stash。
- 切換板件由 Bridge 保存 outgoing Editor draft，再由 Workspace `begin_switch()`／`finish_switch()` 管理 switching invariant；Workspace 本身不執行 UI 或幾何副作用。
- 半初始化測試 fixture 已改用正式 Workspace 依賴，production 沒加入「缺 owner 時回退舊 dict」的後門。
- `.p6fold` schema、UI 操作方式、CornerType／linked EndCap／孔位幾何與 manufacturing resolver 均未改變。
