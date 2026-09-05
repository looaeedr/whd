# Phase6 .p6fold GUI 讀檔驗證 — 2026-08-23

- RED：Footer 無 `讀檔`，`Phase6FoldDesignerApp` 無 `load_project_file()`；兩個 regression 均失敗。
- GREEN：新增 `讀檔`按鈕與 project-load callback，兩個 regression 通過。
- 真檔：`自訂(4).p6fold` 從已開啟 3D 透過「讀檔」載入，主 GUI 與新 3D 恢復 `W/H/D=400/600/250`、`existing_parts=box_body/head/tail`、Door export=False。
- 完整回歸：Xvfb `218 passed, 2 skipped, 4 deselected`。4 個 deselected 仍是既有硬編碼 `/mnt/data/自訂.p6fold` fixture。
- `config.ini`：未修改。


## 2026-08-23 09:21 後續設計更正

本文件記錄的是 08:48 階段「先在 3D Footer 補齊讀檔」的歷史驗證。其 UI 位置已被後續使用者確認的全域設計取代：

- `.p6fold` 開啟／儲存現在是**全域工具列**：主視窗左上角與 modal 3D 視窗左上角都提供 `開啟專案 / 儲存專案 / 另存新檔`。
- 3D Footer 不再顯示全專案 `讀檔 / 存檔`，仍只處理目前板件 transaction。
- authoritative loader、`.p6fold` schema、Windows 雙擊／argv 相容能力仍保留。
- 最新驗證見 `2026-08-23-phase6-global-project-and-corner-lock-verification.md`。
