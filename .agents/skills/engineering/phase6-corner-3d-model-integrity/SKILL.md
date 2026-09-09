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


## 使用者要求驗證板件 / DXF 時

若使用者的目的是「檢查目前板件是否正確」，而不是修改 production，必須轉入：

`[驗證板件與DXF](../驗證板件與DXF/SKILL.md)`

- 「驗目前板件／驗箱身／驗封頭尾／驗門／驗底板」：直接驗 current canonical / features / BEND / 2D-3D owner。
- 「驗中隔」：除通用驗證外，再跑 relief / placement / fixed-hole / FW flush / true-thickness diagnostics。
- 「驗目前板件的 DXF／驗全部 DXF」：實際 export → reopen → compare canonical。
- 「驗全部板件」：從 current workspace/resolved manufacturing output 列舉 physical parts，逐件驗，並核對 expected/actual DXF file count。
- 「完整驗收」：再加 Save→Reload parity。
- 使用者要求「跑一次」時必須真的執行驗收並輪詢 remote run 到 terminal，不得只回歷史 PASS 或目前數值。


## Divider STANDARD topology 與 3D backprojection 邊界（2026-09-09）

- Receiving Divider 的 assembly relief 雖然必須由真實 `box_body:left_side/right_side` physical collision/backprojection 決定「哪一端需要切、實體干涉深度多少」，但 **raw triangle intersection / convex hull 絕不是製造 CUTTING topology authority**。
- STANDARD 的製造拓撲仍由 Fold/material semantics 決定：從材料外緣到 relevant innermost Fold boundary；對目前 Receiving Divider 即由 semantic `core_physical_segment.flat_band` 決定 pre-core boundary。禁止把某次 `core_start=41` 當 magic number；必須每次由 Fold contract 推導。
- Collision linework 必須先 fit 回穩定的 manufacturing topology；triangulation vertex 不得創造斜邊、新 stage 或鋸齒。若 STANDARD 是正交 one-level relief，最終 CUTTING 邊只能沿 Fold/material 軸。
- 真板厚轉換仍由 authoritative `T` 推導 `T/2` skin→solid sweep；只沿實體 inward 方向擴成 solid footprint。禁止用 EndCap/Divider 驗收後量到的差值反補。
- Refold/replay 的零非法穿透是 promotion gate，不是 topology oracle：一個帶錯誤斜邊的 convex hull 也可能 replay GREEN，因此必須同時驗「manufacturing topology 正確」與「post-refold illegal penetration=0」。
- 回歸必須至少鎖：
  1. Fold semantic pre-core boundary；
  2. physical backprojection-derived skin depth；
  3. `T/2` physical-solid conversion；
  4. CUTTING 無 triangulation-generated non-axis edge；
  5. 2D/單板3D/Assembly/DXF 共用 canonical final material。
- Issue #71 的第一輪「disconnected regions 被 hull bridge」假設已由 remote RED run `34345831526` 否證，屬 **REVOKED hypothesis**；不得寫入 production 或未來技能當既定根因。

## Divider Issue74：source Fold 真板厚穿透與 nominal 截角尺寸（2026-09-09）

> 本節 **SUPERSEDES** 上方 Issue71 中「所有 core_start 之後交線皆視為合法 contact」與「Receiving Divider 永遠 one-level pre-core relief」的過度簡化。Issue71 的「禁止 triangulation 斜邊」仍有效。

- `core_start` 是 Divider Fold datum，不是 collision legality boundary。即使 Divider UV 已超過 `core_start`，只要 real `box_body:left_side/right_side` 的某個 semantic Fold band **跨過兩張 physical skins**，仍屬 true-thickness penetration，不能標成 retained contact。
- 單側 skin intersection 只代表 contact witness；例如目前 Receiving 的 `fw_left/fw_right`、`d_left/d_right` 是單側接觸，不得因此擴大 CUTTING。
- Production 的權責分工：
  1. real source piece + semantic Fold band + both-skin crossing → 只決定「哪個 Fold band 真穿透」；
  2. authoritative source Fold lengths + Divider Fold datum + authoritative `T` → **計算 nominal manufacturing dimensions**；
  3. pre-solve physical footprint → 只做 coverage gate；算出的 nominal cut 蓋不住時 **fail closed**，禁止用 probe miss/delta 回補；
  4. post-refold retained material 與 pre-solve true-solid footprint 的 **positive-area overlap 必須為 0**；邊界交線本身可為合法貼合。
- 真板厚規則必須分情境：
  - 若只有 mid-surface / single skin，要由 authoritative `T` 做正確 skin→solid 轉換；
  - 若 source Fold band 的 **兩張 physical skins 已共同界定 true-solid footprint**，就已含 source 板厚，禁止再對同一 footprint 額外加一次 `T/2`，否則就是重複補償／多切。
- Receiving 左右前口的 nominal topology 由 semantic keys 推導，不讀 probe bbox：
  - 左 primary：`U = core_start + zl2_material`；`V = fw_left_material + T/2`；
  - 左 secondary：中心 `U = core_start + zl2_material`，寬 `T`；V 從 `fw_left_material` 到 `fw_left_material + zl1_material`；
  - 右 primary：`U = core_start + zr2_material`；`V = fw_right_material + T/2`。
- 目前使用者 fixture（只作 evidence）為 `core_start=41, zl1=22, zl2=20, FW料=25, zr2=16, T=2`，因此 nominal 結果是：
  - 左 primary **61×26**；
  - 左 secondary **X=60..62、V=25..47**，相對 primary 再深入 **21**；
  - 右 primary **57×26**。
  上述 `61/26/60..62/47/57` 全部是本 fixture 由公式重算出的結果，**禁止硬編成 production 常數**。
- `boolean_margin=0.0005` 類數值只屬 polygon boolean robustness，不是多切量、不是 clearance、不可顯示成製造尺寸。


## Divider Issue74 physical-solid correction（2026-09-09，SUPERSEDES 前一版 nominal 公式段）

- **SUPERSEDES** 本 Skill 先前 Issue74 中「source 兩張 physical skins 已含板厚，因此不得再做 T/2」的過度簡化。正確分層是：
  1. source 兩張 skins 只證明 **source sheet solid** 的真穿透 footprint；
  2. 該 footprint 是 backproject 到 **Divider target skin** 的 UV；
  3. Divider 本身仍是有厚度的 target sheet solid，因此必須再由 authoritative `T` 對 **target** 做一次 `T/2` inward skin→solid sweep。
- 禁止把 source T 與 target T 混成同一次補償。source both-skin 已含 source thickness；target `T/2` sweep 是另一個實體，兩者不能互相抵銷。
- Receiving Divider 的 manufacturing extent 必須直接由 physical collision/backprojection → target `T/2` solid sweep → external-edge-connected orthogonal CUTTING 推導；**不得用 `W/FW` 閉合式、EndCap 742、fixture expected 或 probe delta 當 production 尺寸來源**。
- EndCap Head/Tail middle parity 只做 validation gate：可證明 collision-derived Divider 是否正確，但不得反向決定 cut depth。
- 2026-09-09 final physical acceptance run `34353654567`：
  - Issue74 physical exact **3 PASS**；
  - Divider topology guards **9 PASS**；
  - Xvfb resolved Head/Tail parity **1 PASS**；
  - current fixture physical evidence：primary skin depth 約 26，target `T/2=1` 後 solid depth 約 27；left secondary skin depth約47→solid約48；Divider middle約741.999，Head/Tail 742.0；
  - `0.001` 只屬 boolean fringe / test tolerance。


## Receiving FW formed-solid hard gate（2026-09-09）

- 使用者／family 已確認：Receiving `FW` 輸入是**成形包外尺寸**；例如 `FW=29, T=2` 時 canonical material flange 為 `25`，但 3D formed physical occupation 必須仍為 `29`。
- **FW 都是同一個實體面。** BoxBody left/right FW、Divider FW placement 與 assembly collision 必須使用同一 physical formed-face authority。
- 禁止把 Fold Profile 的 material `len=25` 直接當成 3D formed FW occupation。若 3D world geometry 量到的 formed FW occupation 與 physical contract `outside_dimension` 不一致，必須 **fail closed before Divider collision**。
- Divider relief 不得在錯誤 FW solid 上繼續求解；任何後續 `27`、middle parity、post-refold GREEN 都無效。
- 永久回歸必須至少驗：`fw_left`、`fw_right` 的 3D world formed occupation == family physical contract outside FW，且左右同面。


## 2026-09-09 — Receiving Divider final CUTTING oracle（獨立驗證）

- 對已核准的 Receiving reference fixture，產品／製造驗收值固定為：
  - 左主截角：`61 × 27 mm`
  - 左副階：`2 × 22 mm`
  - 右主截角：`57 × 27 mm`
- `22` 是左副階段長；`48` **不是**核准的製造截角尺寸。
- 這些值只屬 validation oracle；production collision/relief 不得 import/read `tests/**`、不得引用這些 expected 常數、不得由 expected-actual 差值反推補償。
- 驗收必須直接量 `nominal blank - final material` 的最終 CUTTING 輪廓。只驗 metadata（例如 `solid_depth`、`verified=true`、collision evidence）不夠；metadata 與最終 CUTTING 不一致時以 final material 為 QA 判定表面。


## 2026-09-09 — Issue74 COORDINATE-DOMAIN CORRECTION（SUPERSEDES 舊 25→47→48 段）

- **撤銷舊 authority**：任何舊段落若寫出「secondary V = `fw_left .. fw_left+zl1`」、`25→47`、或「`47 + T/2 = 48` 為製造深度」，全部視為 **SUPERSEDED / INVALID**。
- `FW material=25` 屬 **flat/material coordinate domain**；它可以描述展開材料段，但**不得**直接作為 resolved final CUTTING 的 secondary-stage 起點。
- final CUTTING 的 stage placement 必須在 **final-manufacturing coordinate domain** 內解析。若 secondary stage 接續 primary relief，起點 authority 是已解析的 primary CUTTING boundary / physical adjacency，不是 flat FW material datum。
- 禁止把 target-UV 的絕對座標（例如某 footprint 的 `y1=47`）命名成「depth=47」；絕對座標、區段長度、從材料外緣量的深度是三種不同量，任何跨域換算都必須有明確 geometric transform。
- `T/2` 只能做真實 skin→solid 幾何轉換；不得對「絕對座標」直接做 `+T/2` 後宣告為製造截角尺寸。
- QA 必須同時檢查：
  1. material-space 與 final-CUTTING-space 變數／證據有明確 domain；
  2. production 不得用 material FW 作 final notch anchor；
  3. final CUTTING 直接量測通過獨立產品 oracle；
  4. 舊 `25/47/48` evidence 不得再作 current authority。
