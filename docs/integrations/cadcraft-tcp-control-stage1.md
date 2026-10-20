# WHD #1959 — CADCraft v0.8.0 TCP 控制實驗（第一段）

狀態：隔離試作，**不是** WHD GUI 整合／人工操作／製造驗收。

## 已有正式來源

- 既有 \`cadcraft_command_preview_bridge.py\`：由 WHD ResolvedFeature 轉為 CLI 指令、產生隔離 DXF、啟動 CADCraft GUI。
- 既有 \`cadcraft_manual_hole_return_bridge.py\`：僅在來源/尺寸/碰撞檢查通過後進入原 WHD Session，再由原主編輯器提交。
- 官方 CADCraft v0.8.0 \`docs/control-protocol.md\`：桌面程式以 \`--control PORT\` 開啟 **127.0.0.1 TCP JSON Lines**，與 HTTP 不同。
- 官方 \`crates/engine/src/cmd/inquiry.rs::run_inspect\`：\`drawing.inspect\` 包含 \`entityCount\`、\`counts\`、\`space\`、\`skipped\`、\`dirty\` 和限量 \`entities\`，各 entity 有 handle、type、layer、geometry。

## 本段新增

\`gui_modules/editors/cadcraft_control_bridge.py\`：

1. \`CadcraftControlClient(port)\`：固定連 localhost，一次一行 JSON 請求／回覆，核對 request id、明確 \`ok\`、frame／最大長度；禁止未列入範圍的方法。
2. \`probe()\`：讀 ping、方法、命令目錄，驗證所需 method 存在。
3. \`inspect()\`：若回傳的 entity 清單遭截斷、有跳過記錄、重複 handle、不認得的結構，即 fail closed。不把 entityCount 誤作本圖空間清單的 count。
4. \`execute_whd_draw()\`：僅從既有 \`DrawInstruction\` 型別產生 circle／pline，且必須先讀到沒有任何圖元且不是 dirty 的 Model 畫布。所有指令在送出前先核對形狀及數值。
5. 沒有自動重試：官方 timeout \`may-have-run\` 表示操作可能已執行，應銷毀隔離圖面重新開始，不可重送以免多打一個孔。

\`tests/test_issue1959_cadcraft_tcp_control.py\` 使用真 loopback socket 的假伺服器測協定格式、完整讀回、截斷、未知內容、timeout、重複 handle、無效孔型及空白圖保護。加入現有 Linux／Windows CADCraft CI。

## 未實作／不可宣稱通過

- 本段未將 TCP 連線接進 Tk 按鈕，也沒有實際開啟 Windows CADCraft GUI。
- \`drawing.inspect\` 的 raw geometry 目前只是**讀取證據**，尚未進行各實際孔型的完整 geometry parity，**不得**將快照直接匯入 WHD Feature。
- 尚未實作由 TCP snapshot 的移孔、新孔、刪孔到 \`Phase6HoleEditorSession\` 的交易接線。保留現有隔離 DXF + WHD Session 回傳流程，正式製造仍由 WHD 執行。
- \`execute_whd_draw\` 只在 caller 為隔離空白 CADCraft 會話時可用。中途失敗可能已部分繪入該會話，必須丟棄該外部草稿；沒有自動回滾保證。

## 下一段驗收

對實際官方 v0.8.0 GUI，使用隔離程序 \`--control PORT\`、\`probe()\`、\`inspect()\` 取得真 entity payload，建立只接受 Circle/Polyline 且有 mm 與板件 revision 的映射及逐幾何 parity；再把原本手動儲存/回傳改成新按鈕路徑。驗證取消、過期、程序退出、SAVE/RELOAD、原 2D/3D／製造 CUTTING；未取得 Windows 本機 UAT 前不得宣稱正式可用。

產品整合目標 \`localX\`。**沒有本次 /推推，不動 X。**
