# Phase6 統一開孔編輯器交易狀態機最終驗證

## 驗證範圍

本輪驗證 `Phase6HoleEditorSession` 與 `gui.py::_open_unified_hole_editor()` 的交易所有權收斂，確認不改變既有孔位幾何、Door/Indicator、3D、ProjectSession 與輸出資料鏈。

## 核心所有權

- `phase6_hole_editor_session.py` 不 import Tk、GUI、AE renderer、ProjectSession、SettingsService 或 FinalScene。
- `_open_unified_hole_editor()` 不再建立 `selected / active_snapshot / undo_history_ref / context_feature_lists / context_original_features`。
- `_open_unified_hole_editor()` 不再直接 `append / delete / item assignment` 修改 `feature_list`；所有 mutation 經 `HoleEditorAction`。
- 舊 `EditorUndoHistory` 已從 `gui.py` 移除。
- `feature_list` identity 仍是 caller 原本 mutable list，Session 不建立第二份正式 feature source。

## TDD / Session 契約

`tests/test_phase6_hole_editor_session.py` 共 16 項，涵蓋：

- insert → Cancel Active。
- insert → Commit → Undo。
- transient replace → Cancel。
- immediate committed replace → Undo。
- delete → Undo。
- context switch 取消 transient edit。
- Cancel All / Confirm All 多 context 行為。
- round preview transaction 的 Cancel / Commit / Undo。
- Undo 上限。
- ownership AST guard。
- 真 Tk：選取 → 刪除 → Undo → 再刪除 → Cancel All。

最終結果：`16 passed`。

## 原始完整 suite

執行：

```bash
xvfb-run -a python -m pytest -q
```

結果：

```text
349 passed, 2 skipped, 4 failed
```

4 個 failure 全部是既有外部 fixture `/mnt/data/自訂.p6fold` 不存在：

1. `test_uploaded_custom_project_proves_legacy_scene_was_not_using_saved_five_segment_chain`
2. `test_loading_uploaded_custom_project_does_not_reinflate_five_segments_to_legacy_nine`
3. `test_real_main_2d_result_uses_loaded_authoritative_box_fold_chain_width`
4. `test_real_delete_confirm_readd_linked_tail_confirm_roundtrip`

沒有新增功能 failure。

## 完整 0-failure suite

明確 `--deselect` 上述固定 4 項後執行完整 suite：

```text
349 passed, 2 skipped, 4 deselected, 0 failure
```

## 語法與設定檔

- `python -m py_compile gui.py phase6_hole_editor_session.py tests/test_phase6_hole_editor_session.py`：通過。
- `config.ini` SHA256：

```text
5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d
```

與基準相同，未修改。

## 結構結果

- `phase6_hole_editor_session.py`：274 行。
- `_open_unified_hole_editor()`：1494 行 → 1431 行。
- 巢狀函式：63 → 61。

本輪刻意不追求把 Canvas/Tk View 大量搬檔；只先把真正的 transaction state machine 收斂成深模組。下一階段若要繼續，才適合評估 Canvas View／hit-test／reference overlay 的 adapter seam。
