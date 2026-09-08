---
name: phase6-corner-3d-model-integrity
description: Use whenever modifying Phase6 截角、避讓、AssemblyJoint、Fold/placement、3D 單板或組合圖、碰撞求解、FinalScene，或任何會改變 2D/3D 幾何一致性的功能。
---

# Phase6 截角 / 3D 模型完整性 Gate

## 核心原則

只要有動到**截角**或 **3D 圖 / 3D 幾何**，工作就不只是一個畫面修正。必須同步完善真正的 3D 模型與 canonical manufacturing geometry；不得只讓 2D 看起來正確，也不得只改 renderer 掩蓋錯誤 placement。

唯一資料鏈必須能追到：

`state / Assembly Intent → AssemblyJoint Graph → registry / canonical relief → Final Material → 真實板厚 folded solid → 2D / 單板 3D / 組合 3D → DXF / NC → Save / Reload`

## 觸發條件

符合任一即必須套用本 Skill：

- 改任何 CornerType、截角公式、預留量、relief、notch、cut polygon。
- 改 INSERT / OVERLAY / INSERT_OVERLAY / WRAP 或 AssemblyJoint subject / target / region。
- 改 Fold Profile、板厚、placement、mirror、Head / Tail orientation。
- 改單板 3D、組合 3D、FinalScene、mesh、BEND line、碰撞顯示。
- 改多片箱身、piece-level UV、relief owner/backprojection。
- 修任何「2D 對但 3D 錯」或「3D 對但展開/輸出錯」問題。

## 3D 模型硬性契約

1. **真實板厚**：碰撞與包覆判斷必須建立 true-thickness solids；不得用中面相交或 bbox 當最終機械答案。
2. **合法接觸 / 非法穿透分離**：面貼合、WRAP contact 等合法接觸不得當成 collision；正體積非法穿透才進 relief。
3. **求解前證據**：需要自動避讓的案例，必須保留求解前 collision / penetration evidence，不能從已截好的料反推「本來沒碰撞」。
4. **求解後證據**：正式 retained material 必須驗證**零非法穿透**；只證明截角尺寸變了不算完成。
5. **Head / Tail**：語意上下與 physical top/bottom mirror 必須分別驗證，禁止用一端通過推定另一端。
6. **多片箱身**：每片實體有自己的 piece-level UV / world transform / owner；aggregate solid 只可做必要的總體碰撞，不得偽造跨片 UV。
7. **WRAP**：WRAP 是 Joint relation；合法包覆 contact 保留，已認證 WRAP 公式 runtime 直接使用 registry，3D 作 discovery / shadow / regression，不得每次重新發明公式。


## 驗證與 Production 計算來源邊界（硬規則）

**驗證只能拿來判定 production 算得對不對，不能反過來成為 production 的計算來源。**

- Validation / QA / regression 的角色只有「判定結果是否符合 requirement 與 authoritative geometry」。`pytest expected`、驗收量測值、fixture output、probe delta、PASS/FAIL log、截圖、差值、tolerance 都是**證據／oracle**，不是製造輸入。
- Production 公式、offset、補償量、branch selection、placement、relief、hole transform 必須從獨立的 authoritative source 推導，例如：使用者／產品規格、canonical state、Cabinet Family/Topology、Resolved AssemblyJoint、Certified Registry、authoritative `T`、DXF 已授權 feature/datum、真實 physical geometry、collision/backprojection、canonical resolver。
- 若 validation 顯示「實際值 A，期望值 B」，**禁止計算 `B-A` 後把差值塞回 production**；正確動作是追 Source of Truth → derivation → resolved geometry，找出哪個 authority/data-flow/公式錯誤。
- Test tolerance 只存在 assertion 邊界。boolean fringe、floating-point epsilon、solver probe 誤差、近似量測差不得升格為 manufacturing compensation。
- Production code 若 import/read tests、fixtures、expected constants，或出現與單次驗收差值相同的 magic number 來讓測試變綠，直接視為 **fail-closed 架構違規**。
- 只有某數值另有**獨立 authoritative provenance**，並正式進入產品規格／registry／canonical state 後，production 才能使用；「測試剛好量到同一個數字」本身永遠不構成 authority。

## Registry 與新增語意

- 回歸矩陣必須由共用 **registry** / semantics 自動枚舉，至少涵蓋 `INSERT / OVERLAY / INSERT_OVERLAY / WRAP`。
- **新增任何 Assembly Intent** 或 Joint relation 後，必須自動加入參數化回歸；禁止靠手工白名單永遠只列目前四種。
- Registry HIT 的已認證算法是 canonical 製造答案；3D shadow 只能驗證，不能偷偷覆寫。
- Registry MISS 才可進 3D discovery；PROVISIONAL 結果不得直接冒充 CERTIFIED。

## 每次修改後必跑

1. Head / Tail 各自測。
2. 求解前碰撞顯示仍可看到真正 collision。
3. 求解後零非法穿透。
4. **2D / 單板 3D / 組合 3D** 使用同一份 final material，尺寸與截角一致。
5. Fold/BEND 線與 material cut 後的有限 span 一致，不得跨空洞折彎。
6. 每片板金展開料從 final material 量；多片箱身逐片量，不用 exploded preview 包絡冒充一張料。
7. Save / Reload 後 Joint、rule/revision、截角、3D placement、展開料一致。
8. DXF / NC / 批次輸出若在本次資料鏈範圍內，必須消費同一 canonical geometry。
9. 使用實際 `.p6fold` fixture 與 synthetic matrix 都驗證。
10. 至少產生一份可視 3D 檢查圖並由開發端自行檢視；不得把第一輪視覺驗證責任丟給使用者。
11. `config.ini` SHA256 不得改變，除非使用者明確要求。

## 禁止事項

- 禁止只改 2D 截角、不修 3D solid / placement / collision chain。
- 禁止只改 3D renderer 讓錯誤模型「看起來對」。
- 禁止用 legacy 固定截角結果、triangle bbox 或畫面像素當 Source of Truth。
- 禁止把完整回歸責任丟給使用者逐種類手測。
- 任何上述 gate 有紅燈都**禁止交付**或打包成正式版。

## Receiving EndCap D 補償防漂移（2026-08-30 追加）

- 受電箱 EndCap D 核心是 `D - 2T`；金庫型既有 `D - 3T` 不得直接套入 Receiving。
- 任何從 EndCap profile / material core 反推全域 D 的 seam，都必須透過 Cabinet Family policy 取得 compensation，禁止 caller 硬寫 `2T` 或 `3T`。
- 修改 Receiving EndCap / profile / part-switch 後，必跑「Head↔Tail 至少 10 次」穩定性回歸：全域 D、canonical final material 與展開料不得因單純切換而漂移。
- Cabinet Family 切換必須同步 live globals、workspace profile 與 Family topology；Receiving merge 後不得殘留 Vault-only `zr1`。

## Combined Acceptance 與驗證來源硬閘門

1. **先合流再 Combined**：所有已接受 production/regression heads 必須是同一 Combined tested head 的 ancestors。不同 branch 各自 GREEN 不得相加當整體 GREEN；任何 `diverged` 都必須先 non-force merge / 明確三方解衝突，再重跑 Combined。
2. **衝突不能整檔選邊**：若兩票同改 manufacturing / Fold / FinalScene owner，必須逐 hunk 保留雙方 contract，禁止 force-reset 或整檔覆蓋。
3. **驗證不是計算來源**：pytest expected、reopen 實測、collision probe、bbox、solver fringe、rendered number 只能做 acceptance evidence，不得回灌 production geometry。
4. **禁止 magic observation**：`0.001` fringe、`10/100`、`47/26`、`1 mm`、middle-segment 等若只是測試/量測觀察值，不得出現在正式 relief/hole/placement/thickness 推導。
5. **正式來源不變**：production 仍只能讀 canonical state、Fold topology、AssemblyJoint、physical collision/backprojection、authoritative thickness `T`、certified registry/semantics。
6. **cleanup drift gate**：Combined terminal GREEN 後若還有 docs/state/workflow cleanup，必須逐 production/test blob 比對 tested head；任何 production/test drift 都使該 GREEN 失效並要求重跑。
