# #1819 Windows localX 實機驗收（手動啟動）

這是**可選的 Windows 實機量測入口**。程式不會自動執行、不會更動你的正式 X，也不會替你發布。雲端 #1894 的 Xvfb 30 輪數據與這份 Windows 量測必須分開記錄。

## 操作

1. 先在 Windows 將 GitHub localX 以既有 fast-forward 更新方式同步到本機 `Z:\localX`，切換到 `localX` 分支。此步驟不在腳本內做，不會由腳本 pull、push 或 merge。
2. 確認 Windows 有 Git 與可執行 Tkinter 的 Python。批次檔會在當次報告資料夾建立**隔離虛擬環境**（沿用已安裝的 Python GUI 套件）；若缺少 `psutil` 等量測依賴，僅在隔離環境透過 pip 安裝，不更動全域 Python 或原 `localX` 工作區。無法連網或套件安裝失敗時會保留實際錯誤，不能標示成功。
3. 關閉其他正在使用的 WHD 實例，避免量測數據混入其他工作。
4. **自行雙擊** `Z:\localX\tools\issue1819_windows_gtk_uat.bat`，確認提示後才開始。腳本會從當下已檢查的 localX HEAD 建立隔離的、detached 的 Git worktree，並在那裡啟動原有真實 Tk/3D 量測工具。
5. 量測對 3 連與 1 連各跑 30 輪，記錄多連尺寸變動、返回 3D、2D 預覽、解算與快取命中、RSS 檢查點及實際操作延遲。
6. 報告在 `%USERPROFILE%\Documents\WHD_1819_UAT_<token>\`，包含 `windows-real-gui.json`、各 worker 原始 JSONL、`dependencies.log`、`env_setup.log`、`runner.log`、`worktree.log` 與 `manifest.txt`；驗收時以此為證據。先檢查 `env_setup.log` 確認 Python 環境，真正 GUI/製造測試結果才以後續原始記錄判定。

## 安全範圍

- 只有使用者明確確認 Y 後才執行，按 N 就退出；不會自動啟動 GUI 壓測。
- 腳本必須從 Windows `localX` 執行，拒絕其他分支；測試在臨時 checkout 跑，並在完成後移除，**不改動你真正的 localX 工作目錄**。
- 不執行 Git push／pull／正式發布，不會操作 RC、CoreELEC 或 Desktop Commander。
- 執行失敗會保留原始 worker 紀錄供除錯，不能當 GREEN。外部程序可能使 Windows GUI 操作暫時變慢，因此應由使用者選擇適當時間手動啟動。
- 報告仍須檢查每個 worker 30 輪是否完成、有無 Tk 回呼錯誤與 RSS 的實際趨勢。單次成功、malloc/OS 記憶體保留和雲端成功，皆不能直接當成使用者主觀流暢度或長期記憶體穩態證明。
- 原始 CADCraft 進階編輯與完整視窗內嵌不在 #1819 範圍，另屬 #1820 後續評估。

執行 Windows 實測與操作驗收前，#1819 的 Windows UAT 狀態應維持 **PENDING**，正式 X 仍需使用者之後明確下達 /推推。
