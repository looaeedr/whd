# 📚 ㄚ凱的個人 AI 檔案庫 (Personal AI Profile & Context OS)

> 基於「AI 模型會過時，但個人檔案庫可以用一輩子」的核心理念構建。
> 具備 **「雙向反饋與自我演化機制」**，讓 AI 不僅能精準執行當前任務，更能在每次對話糾錯、踩坑與反饋中持續進化。

---

## 🏗️ 檔案庫架構

```
個人AI檔案庫/
├── README.md                                 # 檔案庫導覽、跨平台指南與反饋機制
├── 第一層_核心檔案/                            # 👤 長期核心資產（換模型也不變）
│   ├── 01_個人背景與身份.md                   # ㄚ凱的角色定位、整合專案資產、技術棧
│   ├── 02_溝通風格與輸出偏好.md                # 結論先行、精簡俐落、繁體中文規範
│   ├── 03_核心目標與近期重點.md                # 整合系統優化、無人值守自動化
│   ├── 04_全域AI協作規則.md                   # 高防護模式、Pre-Edit 備份、反饋閉環
│   └── 05_反饋學習與自我演化機制.md            # 【核心反饋】4 步反饋閉環、主動糾偏與規則固化
└── 第二層_專案與SOP/                          # 🛠️ 專案模組與標準作業程序
    ├── 01_DXF與CAD自動化全域規範.md            # 鈑金加工圖層（CUTTING/BEND/MARKING/CHECK/STOCK/DATUM）
    ├── 02_通用任務SOP模板.md                  # 新專案 / 任務快速建立規範模板
    ├── 03_常用Prompt指令庫.md                 # 整合管線、幾何展開、反饋沉澱指令
    ├── 04_WHD鈑金展開幾何引擎規範.md           # ae_engine 套件：Shapely 拓撲展開、Base-Relief、CornerType
    ├── 05_CAD批次拆圖與特徵萃取規範.md          # 拆圖管線：大圖框辨識、氣切視圖分離、底座獨立拆分
    └── 06_踩坑記錄與防錯經驗庫.md              # 【實戰反饋庫】歷史踩坑教訓、反面教材與避坑指南
```

---

## 🔄 核心亮點：反饋與自我演化閉環 (Feedback Loop)

檔案庫不是靜態的說明書，而是透過以下機制持續學習：
1. **被糾正時自動觸發**：當 ㄚ凱 糾正 AI（如「不對，應該是...」）時，AI 自動執行【糾偏 → 根因剖析 → 規則固化 → 寫入檔案庫】。
2. **程式修改即同步文件（強制）**：只要本輪新增或修改了幾何規則、資料契約、UI 行為、2D/3D/DXF、`.p6fold`、加工邏輯或修復了可重現 Bug，必須在**同一輪交付**直接更新對應 SOP；若屬踩坑/反例，必須同步追加至 `06_踩坑記錄與防錯經驗庫.md`。**不得等待使用者再次提醒「更新文件」。**
3. **程式與規範同版交付**：程式 ZIP/PATCH 與本輪修改後的規範必須保持同一語意版本；若規範內容已落後程式，交付前先更新規範，不得把已知舊規則繼續當成正式契約。
4. **防錯經驗沉澱**：所有歷史錯誤、根因與避坑要點記錄於 `06_踩坑記錄與防錯經驗庫.md`，避免跨模型、跨平台再次重犯。
5. **無對應章節時直接新增**：若新規則沒有合適章節，應在最接近的第二層 SOP 新增清楚章節；必要時新增專用 SOP，而不是把規則只留在聊天或程式註解中。

---

## 🌐 跨平台載入指南

### 1. Claude (Claude 3.5 Sonnet / Opus)
- **Claude Projects** → Project Knowledge 上傳所有 `.md`。
- **Project Instructions**：「你是 ㄚ凱 的資深副駕駛，請依據 Project Knowledge 內的整合管線、幾何規範與反饋演化機制協作。」

### 2. ChatGPT (GPT-4o / o1)
- **ChatGPT Projects / GPTs** → 打包上傳整個檔案庫。

### 3. Google Gemini
- **Gemini Gems** → 建立名為「ㄚ凱副駕駛」的 Gem，將核心檔案重點載入 Instructions。

### 4. 本機 AI Agent (Antigravity / Cursor)
- 常駐於工作目錄，每次任務皆自動調用、嚴格遵守並即時同步反饋。

## 🗂️ 原始檔名與結構保留（強制）
- 使用者提供的個人檔案庫、SOP、規格文件在更新、合併、打包時，**必須保留使用者原本的中文檔名與既有資料夾結構**。
- **不得為了 CLI、ZIP、跨平台或編碼方便擅自改成英文／ASCII 檔名**；若遇到相容性問題，應修正 UTF-8 / ZIP 寫入方式，而不是改名規避。
- 只有使用者明確要求重新命名時，才可變更檔名或目錄名稱。

## 🆕 2026-08-23 最新固化
- 箱身 ↔ 封頭／封尾四條已確認機械基準：接合鏈外側刪折同步、上方 CornerType 即組合語意、貼外每端占 1T、5 段 `FW-D-W-D-FW` 對應 Head `FW-D-後折` / Tail `後折-D-FW`。
- AI 證據優先級：使用者已確認的機械關係高於目前程式／測試；「沒有重新驗證」不能被偷換成「規則可能錯誤」，禁止用 AI 自己寫入的程式／測試做循環論證。
- Fold Chain：**操作員輸入幾度就折幾度**；封頭／封尾 derived profile 不得固定改成 90°。
- 視角不參與折角幾何；禁止以 projection 修補 angle bug。
- Phase6 commit 後主 2D 必須直接回到同一 FinalScene。
- 板件按鈕單擊一次直接進入；「刪除板件」位於板件按鈕區正下方。



## 🆕 2026-08-27 最新固化
- **Assembly 3D 必須有使用者看得到的正式入口（舊版入口已廢止）**：曾使用頂部 `單件 / 組合體` 兩顆按鈕；此做法已被 2026-08-27 最新規格取代。現在唯一正式入口是左側 `板件選擇` 第一項 `組合體`，第一次進 3D 直接選中組合體；不得恢復第二套模式按鈕。
- **第一階段組合體範圍固定為箱身 + 封頭 + 封尾**：門、底板不混入 BoxBody/EndCap collision assembly，避免無關板件遮蔽接合幾何。
- **Shared Assembly World Geometry**：`ae_engine/assembly_geometry.py` 是折後 mesh 與 assembly placement 的共同 Source of Truth；3D Viewer 與 collision 端不得各維護一套 folding / placement。
- **交付 ZIP 禁止 `#Uxxxx` 路徑**：中文檔名與資料夾必須以真正 Unicode/UTF-8 ZIP entry 保存；交付前必須檢查 ZIP entry 不含 literal `#U` escape，並實際解壓驗證 `新WHD/個人AI檔案庫/...` 等中文路徑存在。

## 2026-08-27 最新 3D Designer UI 固化
- 第一次進 3D 直接顯示 `組合體`；`組合體` 是左側 `板件選擇` 第一項，不再另設 `單件/組合體` 模式按鈕。
- 組合體目前只顯示 `箱身 + 封頭 + 封尾`；選任何實際板件即回到單件編輯。
- 組合體方向基準：組合方式先解析成 authoritative Fold Profile；EndCap local `z=0` 是**板厚中心面**，local `+z` 是折邊朝箱內。封頭 +Z 向下、封尾 +Z 向上且保留 Tail native X/Y orientation；Tail Fold Profile 已是 native bottom→top，禁止 assembly 二次上下鏡射。實體接合不再用 z=0 直接貼箱身，而是以真實 `T` 建立內外 skin，中心面向箱外偏移 T/2，讓內側 skin 貼箱身。`OVERLAY` 不得虛構左右 X 折邊；`INSERT / INSERT_OVERLAY` 保留真實左右折邊。共享 assembly geometry 同時供 3D viewer 與 collision 使用。
- 組合體切換板件：assembly 可用 `box_body` 作幾何 backing，但從 `組合體` 點 `箱身` 時仍必須完整切到 single mode；不可因 backing active part 已是箱身就 early-return。
- **EndCap 組合體 3D 必須是實體板，不是零厚度中心皮**：標準未修改金庫型封頭／封尾保持完整 X 2 + Y 3 = 5 道 BEND；Fold Profile 先折成 mid-surface，再以真實 `T` 建立內外 skin。Head/Tail 中心面向箱外偏移 T/2，內側 skin 貼箱身、外側成型面在箱外，折邊朝箱內；不得再把 `z=0` mid-surface 直接當 mating face。
- 最上列：`檔案 ▼ / 3D 顯示(文字大小、折彎透視、面板透視) / 全螢幕 / 還原初始值`；2026-08-28 起移除 `取消 / 確定`，3D 編輯即時同步 canonical state。
- 全域設定固定兩行：第 1 行 `基準型號 / 參數鎖定 / 儲存預設值`；第 2 行 `W / H / D / T / 結構 / 組合方式`。
- 右側只保留「解鎖後的板件設定／組合體診斷 + 3D 畫布」；組合體模式解鎖時不得誤顯示箱身設定，而是顯示組合體診斷。
- UPDATE 包必須以專案根目錄為 archive root，禁止再多包一層 `新WHD/`。
- GUI 入口唯一真值：正式程式只允許根目錄 `gui.py`；`基準檔/gui.py` 僅可作轉跳器，不得再保存完整舊 GUI，避免更新後仍啟動舊版面。


## 🆕 2026-08-28 EndCap 組合體視覺防錯
- EndCap 加厚為 physical closed solid 後，孔與折彎線不可只從 solid open boundary 判斷；through-hole 邊界與 formed crease 會因封閉實體而變成共享 edge。
- 正式組合體必須從「加厚前、已依 final BEND guides 折好的 mid-surface」抽出外輪廓／孔輪廓與非共面 crease，再疊到 physical solid。
- 標準未修改金庫型封頭／封尾仍是 X 2 + Y 3 = 5 道 BEND；看到 `ytop1` 第一折、留肉折線或孔不見時，先查 renderer edge extraction，不得擅自改 Fold Profile、CornerType 或 CUTTING。

## 🆕 2026-08-28 06:49 EndCap 孔口／折彎線顯示固化
- 前一版「只從 folded mid-surface 疊孔／crease」仍不足：mid-surface 位於實體板厚中間，會被 ±T/2 skin 與後方 BoxBody 遮蔽。
- 組合體 Head/Tail 必須從 **thickened physical solid 的非共面 feature edges** 顯示真正位於外／內 skin 的 through-hole rim、外周與折彎/miter edge；mid-surface crease 只作 fallback。
- 所有 3D `BEND` guide 固定使用**實線**，不得再使用虛線。
- 標準金庫型固定孔仍由 `PartRenderData.material` / CUTTING 擁有；renderer 只能顯示，不得重建或猜孔。


## 🆕 2026-08-28 08:00 組合體固定截角干涉診斷固化
- `參數鎖定` 在組合體模式解鎖後必須顯示「組合體診斷」面板，不能再被 assembly mode 直接擋掉。
- 組合體診斷預設提供 `診斷時忽略固定截角` 與 `顯示干涉碰撞區`；固定截角目前只在診斷視圖補回未退讓外形，**正式 CUTTING / DXF / CornerType 不刪除**。
- 未退讓 EndCap 顯示材料可用 material bounds 補回 exterior relief 並保留 hole interiors；但固定截角碰撞 probe 必須使用 **`restored material - production material` 的 relief delta**，禁止把整片 EndCap 拿去求 surface crossing。
- 整片 EndCap probe 會把正常 mating seam 一起誤判，早期 947 段整圈紅線已判定無效；標準金庫型 delta probe 在本測試環境為 454 段局部交線（Head 227 + Tail 227）。
- 干涉顯示建立在 `ae_engine/assembly_geometry.py` 的共享 world-space physical mesh；紅色半透明面只允許畫命中的 relief-delta triangles，並疊紅色粗實線 intersection segments。
- 關閉 `診斷時忽略固定截角` 時，不得退回整片 production EndCap 做碰撞；應停止此 probe 並提示先啟用固定截角診斷。
- AI 交付前必須自行看過 Head / Tail 視角；紅區若沿正常長接縫擴散即判定不合格，不得叫使用者代驗收。
- `phase6_final_scene_view.py` 不得 import/call production `assembly_collision` solver；viewer 只能消費共享 assembly geometry 的純診斷結果。


## 🆕 2026-08-28 13:04 3D 干涉反投影正式截角固化
- Head/Tail 固定截角不再是最終尺寸 Source of Truth；正式尺寸由 shared world-space physical collision 反投影回 2D flat UV 後求得，並以重新折回 3D 的零材料穿透作 verification gate。
- 淨空 A 在收斂後做精確正交級距擴張；不使用一般 polygon buffer 污染尺寸。
- verified cut 會進 `EndCapPartSpec.resolved_assembly_relief_cuts`，Manufacturing API 先補回 legacy fixed relief 再套新 cut，並重新依 authoritative Fold Profile clip BEND，因此 2D / 3D / DXF 共用同一份 CUTTING。
- 求解結果綁定 W/H/D/T、組合方式與 Fold Profile；任何來源變更都使舊 cut 失效。
- 標準 regression：W500×H600×D200、T2、FW24、A0 = `39×38 + 14×4`；A5 = `44×43 + 19×4`。目前主 GUI 預設標準金庫型 Head/Tail = `40×39 + 14×4`，3D 回折驗證零材料穿透。這些數值只可當測試證據，禁止硬寫成公式。

## 🆕 2026-08-28 19:00 UPDATE 介面同步固化
- `AssemblySceneRenderData` 與 `fold_designer_bridge.py` 是 caller/contract 配對檔；任何新增 constructor field（例如 `show_interference`、`ignore_fixed_corner_relief`）時，UPDATE 必須同步包含介面擁有者 `phase6_final_scene_view.py`，不得只更新 caller。
- UPDATE 不能假設使用者一定逐版套用。至少對前一個可公開取得 FULL 做「舊 FULL + 新 UPDATE」實際覆蓋測試，並由正式 `gui.py -> open_original_fold_designer()` 驗證 `final_scene_view.cutting_mesh_error is None`。
- Caller 對可選 UI-only contract field 應保留 backward-compatible constructor adapter；mixed-version tree 不得因 `unexpected keyword argument` 直接讓組合體 3D 空白。


## 🆕 2026-08-28 21:34 2D / 3D Live Canonical 同步固化
- 3D Fold Designer **移除「確定 / 取消」**；不再建立可 rollback 的 ProjectSession draft。`還原初始值` 保留，並且還原結果立即同步。
- W/H/D/T、組合方式、Fold Profile、CornerType、板件存在狀態、結構參數、EndCap FW、淨空 A 等 production edit 都經 `on_live_sync(payload)` 即時寫回主 GUI 的唯一 canonical state；即時同步只改記憶體，不自動寫磁碟。
- 2D、3D 組合體、DXF/NC 不得各保存自己的 solved material；全部只能由同一份 `PartSpec -> Manufacturing API -> PartRenderData` 重建。3D solver 的 `solved_render_data` 只作 verification reference，不得直接成為 production render。
- Dynamic relief 必須 **Head/Tail 原子提交**：同一輪兩片都 refold verified 才一起寫入 canonical `assembly_relief_state`；任一片失敗時兩片都沿用目前 canonical Manufacturing geometry，禁止 Head-new/Tail-old 半套組合。
- 舊 relief fingerprint 與當下 W/H/D/T/FW、組合方式、BoxBody/EndCap Fold Profile 不符即視為 stale；live sync 會清除 stale production relief。實檔 `自訂(6).p6fold` 已驗證舊 `INSERT` relief 在當下 `INSERT_OVERLAY` 狀態會失效。
- 實檔驗收必須比較主 2D authoritative EndCap material 與 assembly provider material；`symmetric_difference.area` 必須為 0（容差 1e-6），不能只看 3D 畫面「像不像」。

## 🆕 2026-08-29 EndCap 單級 INSERT 38×27 與文件同版固化
- `自訂(9).p6fold` 已確認 Head/Tail 上方單級 INSERT 真實製造截角為 `38×27`；38 是折後 mating boundary 的幾何結果，不得硬寫成固定公式。
- ±T/2 physical skin 的正常貼合帶只能算 contact，不能直接拿外側 skin intersection 當 relief penetration boundary；否則本案會被誤算成約 `38.98×27` 再顯示為 `39×27`。
- 單板 3D 不得在 canonical relief fingerprint 誤判後退回 legacy fixed relief（本案曾出現 `40×27`）。2D / 單板 3D / 組合圖 / DXF-NC 必須共用同一 `PartRenderData.material`。
- 實檔驗收新增硬門檻：Head/Tail solver verified、errors 空、尺寸一致，且主 2D 與 assembly material symmetric difference = 0。
- **交付程序再強化**：任何可重現 Bug 修復若改了程式／測試，FULL/UPDATE 出包前必須同步更新 `修改日誌`、對應 Superpowers verification、AI/SOP 規範與踩坑庫。只交程式 ZIP、事後等使用者提醒補文件，視為交付未完成。

## 🆕 2026-08-29 Certified Relief Registry 固化
- 已知正確 Assembly Relief 必須先查可版本化 Certified Registry；不得再讓每次 3D solver 改版重算並覆蓋既有製造答案。
- `CERTIFIED / CERTIFIED_FROM_3D` 是製造真值；3D 只 shadow validate。只有 registry MISS 才允許 `PROVISIONAL_3D`。
- Registry 存公式＋precondition＋topology＋revision＋evidence，不存單次死尺寸。
- 新組合必須由 registry 自動加入測試矩陣；無 fixture / 無 rule / 未通過 Head/Tail、collision、2D/3D/assembly、Save/Reload，不得交付。
- Save/Reload 必須保存 rule_id/revision/trust；stale/ambiguous rule 不准靜默 fallback。
