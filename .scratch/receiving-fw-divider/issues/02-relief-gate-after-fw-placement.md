# T48-2: 中隔 relief 只能在 FW 面齊後求解與 verified

**What to build:** 將 Receiving Divider relief 的計算與驗證建立在 T48-1 已證明的正確 placement 上；若 placement / FW face-flush 前置條件不成立，不得回傳 `verified=True`。正確 placement 後重新以真實三件式 BoxBody physical pieces 動態求 relief。

**Approved RED IDs:** R3（依賴 R2）

**Requirement Authority:** 使用者核准 R2/R3 為同一根因鏈：FW 面沒齊 → 3D placement 錯 → 錯位置做 collision → solver 仍錯誤 verified。run `34166999592` 顯示 FW 未面齊時仍得到 `verified=True`，且左右約 `1mm` cut；這些 mm 只能算診斷值，不能當規格。

**AI Library References:**
- `個人AI檔案庫/第一層_核心檔案/04_全域AI協作規則.md`
- `個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md`
- `個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md`
- `個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md`
- `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`
- `基準檔/截角資料庫/README_母規則說明.md`
- `基準檔/截角資料庫/certified_relief_rules.json`

**AI Library Writeback:** REQUIRED — 更新 `個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md`：任何 3D relief `verified` 前必須先證明 authoritative placement / mating-face precondition；錯誤 placement 上的 collision result 不得升格。

**Blocked by:** T48-1

**Status:** blocked

- [ ] relief resolver 在正確 Divider placement 後才執行 collision/backprojection。
- [ ] `verified=True` 必須包含 placement/face relation 已成立的 evidence。
- [ ] 使用 `box_body:left_side` / `box_body:right_side` 真實 physical pieces；不得用單一虛擬 aggregate 當 backprojection owner。
- [ ] baseline `中隔.dxf` 仍只提供固定孔，不成為 relief contour oracle。
- [ ] R3 由 RED 轉 GREEN。
- [ ] 不使用 `1mm`、`47/26` 或任何單次 probe cut depth 當固定 oracle。
