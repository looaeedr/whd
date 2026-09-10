# WHD 截角資料與 2D 入口收斂規則

## 已確認產品規則

1. 主視窗舊獨立 2D 入口最終要收掉；新的入口在 Fold Designer 板件選單，名稱固定為「截角資料」。
2. 「截角資料」是 UI mode，不是新板件，也不是第二套 manufacturing state。
3. 3D 有的正式板件，截角資料就有；板件來源只能是 current authoritative workspace / resolved manufacturing output。
4. 點一個板件後，Fold Designer 同一圖區顯示該板件既有展開圖。不得跳回舊 Notebook，也不得另造簡化 2D renderer。
5. 既有 2D 功能全部保留：材料外框、截角、孔、BEND、尺寸、標註、part-specific interaction。只換入口，不換機械計算。
6. stable authoritative part key 是唯一 identity；UI label 只顯示，不得作資料 key。
7. refresh 時合法 selection 保留；板件被移除後 stale selection 必須丟棄並重新 resolve。
8. multipart BoxBody：頂層可顯示「箱身」，physical child 仍各自存在；優先恢復已記住且仍合法的 child，否則使用 authoritative workspace order 第一個 child。禁止 parent aggregate 假裝單片展圖。
9. mode switch / widget destroy-recreate / StringVar trace / selection callback 不得修改 manufacturing state 或重送幾何。
10. dual-view 過渡期由同一 authoritative state 驅動兩個 View refresh，不做 widget-to-widget copy。
11. 舊 2D 移除順序固定「先接、再驗、最後刪」。T7 前 parity 未完成不得提前收掉 legacy entry。
12. legacy dead-code gate 要證明 production navigation 不再依賴 `tab_z/tab_head/tab_tail/tab_door/tab_base_plate` 且沒有 dangling callbacks。
13. Validation / pytest expected / screenshot /量測值只能判定 production 對錯，不能反向成為 production 幾何輸入。

## 目前程式結構事實

- `gui.py` 的舊 2D 為 `ttk.Notebook`，至少含箱身、封頭、封尾、門、底板頁。
- 舊 bridge 仍有 stable key -> legacy tab -> `refresh_corner_type_panel()` / `draw_preview()` 的入口 glue。
- `fold_designer_bridge.py` 已有 `part_selector`、`available_parts`、operator part projection、multipart physical-child helper 與 assembly parts panel，可作新模式骨架。
- physical child render data 已有「同一 resolved aggregate manufacturing result 的 sink」契約，禁止第二次 BoxBody solve。

## 開發/驗收規則

- 每次修改先從最新 target 開新分支。
- 先跑 Phase6 preflight 並讀完 REQUIRED SKILLS / REQUIRED REFERENCES。
- Contract/Adapter RED-first，之後最小 production change。
- 最終要有 headless、Tk/Xvfb、Save→Reload、DXF/physical-part acceptance 與 config.ini invariant。
- 所有新發現的規則與踩坑，要同步 Skill、AI knowledge/library、durable agent docs，不得只留聊天紀錄。
