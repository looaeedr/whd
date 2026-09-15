# PHASE6 最新正確語意總則

> 日期：2026-08-31  
> 狀態：Canonical Semantics / 不依賴目前程式實作狀態  
> 適用範圍：PHASE6 尺寸、Fold Topology、Assembly Intent、AssemblyJoint Graph、STANDARD 截角、Certified Relief Registry、2D / 3D / DXF / NC / Save-Reload  
> 目的：把目前最新、最高優先、最不容易混淆的語意整理成單一可讀文件，供後續 AI 與工程實作使用。

---

# 0. 本文件的定位

本文件只回答一件事：

```text
目前最新、最正確的 PHASE6 機械語意是什麼？
```

它不以目前程式是否已完整實作為準，也不以舊 test 是否仍存在為準。

若程式、舊 regression、舊 Skill、舊 `.p6fold` cache、舊截角資料庫內容與本文件衝突，必須先標記衝突，再決定 migration；不得直接用舊實作反推語意。

本文件的上游依據：

- `PHASE6_組合尺寸截角與JointGraph_整合最高優先規格_20260831.md`
- `基準檔/截角資料庫/README_母規則說明.md`
- `基準檔/截角資料庫/certified_relief_rules.json`
- `基準檔/截角資料庫/certified_relief_rules.schema.json`
- `.agents/skills/engineering/phase6-corner-3d-model-integrity/SKILL.md`
- `.agents/skills/engineering/phase6-overlay-relief-basis/SKILL.md`

本次文件撰寫已讀 Skill evidence：

```text
phase6-corner-3d-model-integrity
phase6-overlay-relief-basis
domain-modeling
writing-for-agents
```

---

# 1. 一句話總模型

PHASE6 的正確資料鏈是：

```text
整體包外尺寸
    ↓
每片 physical piece 的成形包外尺寸
    ↓
每片自己的 material segment chain + 真實 Fold Topology
    ↓
Assembly Intent preset
    ↓
Resolved AssemblyJoint Graph
    ↓
Corner STANDARD
    ↓
Semantic Delta
    ↓
Resolved Manufacturing Geometry
    ↓
2D / 單板 3D / 組合 3D / FinalScene / DXF / NC / Save-Reload
```

三個核心分工：

```text
Dimension Model 決定尺寸在哪一層。
AssemblyJoint Graph 決定板件彼此怎麼接。
Certified Relief Registry 決定已認證截角公式。
```

AI 的 Skill 只決定「AI 怎麼改」。

截角資料庫決定「程式算什麼」。

兩者不能混用。

---

# 2. 尺寸語意

## 2.1 整體包外尺寸

`W / H / D` 是整台箱體完成組裝後，以外側成形面量到的目標尺寸。

它不是料尺寸，也不是某一片板的展開尺寸。

範例：

```text
W = 400
D = 200
T = 2
```

代表完成後箱體外框寬 400、深 200、板厚 2。

## 2.2 板件成形包外尺寸

每片板折完後，會有自己的成形包外尺寸。

它可能等於整體尺寸，也可能因組合關係少一個或多一個 `T`。

範例：

```text
整體 D = 200
EndCap 主面成形包外 D = 198
EndCap 主面料尺寸 = 194
```

這三個值不能混在一起。

## 2.3 料尺寸

料尺寸是展平後某一段 material segment 的長度。

通則：

```text
料尺寸 = 成形包外尺寸 - 實際相鄰折彎數 × T
```

相鄰折彎數不是固定常數，要由當下真實 Fold Topology 判斷：

```text
0 bend -> 不扣 T
1 bend -> 扣 1T
2 bend -> 扣 2T
```

如果某個 preset 讓某條 Fold 不存在，料尺寸必須重算。

## 2.4 折邊尺寸的預設語意

在製造討論中，若使用者說：

```text
折 15
FW 25
內邊框 16
```

且沒有特別說「包外」，預設應理解為料尺寸。

T=2 範例：

```text
料 15 + 1 個相鄰折彎 -> 包外 17
料 16 + 1 個相鄰折彎 -> 包外 18
料 25 + 兩側各 1 個相鄰折彎 -> 包外 29
```

## 2.5 負號不是料長

`-24` 這種值只表示 bend orientation。

正確拆法：

```text
尺寸大小 = 24
方向 = negative orientation
```

負號不能參與料長加減。

---

# 3. Family 的責任

Family 只決定這個箱型有哪些板件、板件怎麼長、target face 在哪裡。

Family 可以決定：

- 箱身是一片、二件或三件；
- 側背是否分離；
- 後面板是不是平板；
- 哪一片是左側板、右側板、後面板；
- 某個 mating face 的實際座標、寬度、方向；
- Receiving 後面板寬度是 `W - 2.5T` 這類 family structure dimension；
- Receiving 下方 target face 來自側板後折還是後面板。

Family 不可以決定：

- `INSERT` 在 Receiving 是另一種意思；
- `OVERLAY` 在某個 Family 還保留 X Fold；
- `WRAP` 在某個 Family 方向相反；
- 下方 WRAP 是 Receiving module 自己的私有 CornerType；
- 同一 relation 在 Vault 和 Receiving 有不同機械語意。

正確分層：

```text
Family Geometry
    -> 提供 actual target face / mating zone
Global AssemblyJoint
    -> 解釋 INSERT / OVERLAY / WRAP 的全域語意
Corner Resolver
    -> 用上述兩者生成截角 delta
```

---

# 4. Assembly Intent 與 AssemblyJoint

## 4.1 Assembly Intent 是 preset

Assembly Intent 是操作員選的高階常用組合方式。

它的角色是產生一組預設 Joint Map：

```text
Intent
    ↓
default_joint_map
    ↓
Resolved AssemblyJoint Graph
```

Intent 不是最終機械真值。

使用者可以改某一邊；solver 或 migration 也可能得到更精確的 edge-level relation。

## 4.2 AssemblyJoint 是真相

AssemblyJoint 描述一個實體對另一個實體的局部機械關係。

它至少要能回答：

```text
誰是 subject
誰是 target
subject 的哪一條邊 / 哪個 region
target 的哪個 face / mating zone
relation 是 INSERT / OVERLAY / INSERT_OVERLAY / WRAP
方向是誰往誰
哪一邊要保留材料
哪一邊要避讓
合法接觸在哪裡
非法穿透在哪裡
clearance / retain / extra cut 的來源是什麼
```

一片板可以同時有多種 Joint。

所以「整片 EndCap 只有一個 `assembly_type`」不夠。

---

# 5. 四邊 Joint Map

EndCap / Tail 主面至少要有四條邊：

```text
TOP
BOTTOM
LEFT
RIGHT
```

每一邊可以指向不同 target part。

Receiving 側背分離時，例子可能是：

```text
TOP    -> 箱身上方接合面
LEFT   -> 左側板
RIGHT  -> 右側板
BOTTOM -> 後面板或下方包覆接合區
```

因此，下方 WRAP 和上方 OVERLAY 同時存在於同一片 EndCap 是正常現象，不是例外。

---

# 6. 目前正確的預設組合語意

## 6.1 INSERT

預設：

```text
TOP    = INSERT
LEFT   = INSERT
RIGHT  = INSERT
BOTTOM = INSERT
```

語意：

```text
四邊預設都進入 target inside boundary / mating zone
```

## 6.2 OVERLAY

預設：

```text
TOP    = OVERLAY
LEFT   = OVERLAY
RIGHT  = OVERLAY
BOTTOM = INSERT
```

語意：

```text
上方與左右貼外面齊
下方仍為嵌入
```

重要：

```text
OVERLAY 預設下 LEFT / RIGHT 是 OVERLAY
=> EndCap X Fold 物理上不存在
```

這不是 UI 隱藏折線，也不是 3D 還偷偷折出側面。

## 6.3 INSERT_OVERLAY

預設：

```text
TOP    = OVERLAY
LEFT   = INSERT
RIGHT  = INSERT
BOTTOM = INSERT
```

它不是「左 INSERT、右 OVERLAY」。

它的上方角之所以形成 `INSERT_OVERLAY`，是因為 corner resolver 在同一上角附近同時看到：

```text
TOP OVERLAY
+ SIDE INSERT
```

因此實際角落語意是：

```text
STANDARD
+ 局部 OVERLAY 留肉 / 面齊
+ 局部 INSERT 多切 / 進內緣
```

## 6.4 包覆貼外

這是一個高階常用 preset，不是底層 relation 名稱。

預設：

```text
TOP    = OVERLAY
LEFT   = INSERT
RIGHT  = INSERT
BOTTOM = WRAP
```

Receiving 常用這組，但它不是 Receiving 私有語意。

若 Vault 或其他 Family 也有相同四邊關係，可以直接共用。

---

# 7. Joint Relation 的語意

## 7.1 INSERT

核心：

```text
subject 進入 target inside boundary / mating zone
```

若 STANDARD 剛好停在邊界，仍可能需要相對 STANDARD 多切出裝配間隙。

但多切量不能憑空猜。

正式值必須來自：

- Certified Relief Registry；
- 已確認 fixture；
- 工法參數；
- 3D discovery 後升級成 certified rule。

## 7.2 OVERLAY

核心：

```text
subject 的局部成形面與 target face 面齊
```

OVERLAY 是 FACE_FLUSH，不是單純「少一條折彎」。

但在目前 EndCap 預設語意下，LEFT / RIGHT 為 OVERLAY 時，X Fold 確實不存在，因為結構變成 flat-X topology。

## 7.3 INSERT_OVERLAY

`INSERT_OVERLAY` 是局部 hybrid。

它只有在同一 corner 或同一局部 mating zone 同時需要：

```text
outer face contact / flush
+ inside insertion / clearance
```

才成立。

不能只因為高階 intent 名稱叫 `INSERT_OVERLAY`，就把整片板所有角都套二級截角。

## 7.4 WRAP

核心：

```text
外側實體包覆內側實體
```

WRAP 必須明確指定：

```text
外側是誰
內側是誰
contact face 是誰
哪裡要保留
哪裡要避讓
哪裡是合法接觸
哪裡是非法穿透
```

WRAP 不是包外尺寸。

看到包外 `18` 不等於 WRAP。

---

# 8. STANDARD 截角

## 8.1 唯一母體

所有截角都必須寫成：

```text
Actual Corner = STANDARD + Semantic Delta
```

不再接受：

```text
INSERT 一套 dead formula
OVERLAY 一套 dead formula
INSERT_OVERLAY 一套 dead formula
WRAP 一套 dead formula
```

## 8.2 STANDARD 的定義

STANDARD 是：

```text
從材料外緣切到該方向最內部的實際折彎線
```

它不是：

- 第一條折彎線；
- 某個 CornerType 的固定數字；
- solver bbox；
- renderer 看起來對的像素結果；
- Family 私有 magic number。

## 8.3 Topology 變時

STANDARD 的規則不變。

但因實際 Fold Topology 改變，最內部折彎線的位置可能改變，所以 STANDARD 幾何會重新計算。

這叫：

```text
同一母規則在新 topology 下重新解析
```

不是改掉 STANDARD。

---

# 9. 上方 EndCap / Tail STANDARD 範例

指定 fixture：

```text
T = 2
左右側折料 = 15
內邊框料 = 16
FW 料 = 25
D 主面成形包外 = 198
D 主面料 = 194
下折料 = 15
```

上方 Y 方向最內折線：

```text
ytop1 + FW = 16 + 25 = 41
```

上方 X 方向最內折線：

```text
side_fold + FW = 15 + 25 = 40
```

所以上方 STANDARD：

```text
40 × 41
```

注意：`41` 不是 FW。

```text
16 = 內邊框料
25 = FW 料
41 = ytop1 + FW 的 cumulative standard depth
```

---

# 10. 下方 STANDARD 範例

指定 fixture：

```text
左右側折料 = 15
下折料 = 15
```

下方 STANDARD：

```text
15 × 15
```

Receiving 下方 WRAP 不是把 STANDARD 改名成 INSERT_OVERLAY。

正確語意：

```text
BOTTOM STANDARD
+ BOTTOM WRAP semantic delta
```

---

# 11. Semantic Delta

Semantic Delta 是相對 STANDARD 的語意調整。

## 11.1 INSERT delta

語意：

```text
從 STANDARD 多切，使 subject 進入 target inside boundary
```

多切量可以是 `T` 倍數或 mm，但必須有正式來源。

## 11.2 OVERLAY delta

語意：

```text
從 STANDARD 留肉，使 subject face 與 target face 面齊
```

目前最新母規則中，OVERLAY 上方 FW band 的正式解釋是：

```text
STANDARD top
+ FW band 留肉 1T
```

對應 fixture：

```text
40 × 39 + 15 × 2
```

`formed FW` 可以作 3D shadow / diagnostic evidence。

但依目前最高優先整合語意，正式 CUTTING 公式不可再直接把 `BOX_BODY_FORMED_FW` 當唯一輸入覆蓋 STANDARD 母體。

這點與舊 Skill 文字仍有衝突，後續若更新 Skill，應讓 Skill 跟隨本文件與 certified registry 的 v3 語意。

## 11.3 INSERT_OVERLAY delta

語意：

```text
STANDARD 上同時存在局部多切與局部留肉
```

它不是一個和 STANDARD 無關的固定二級公式。

`0.5T / 2T` 目前只能視為：

- 已存在歷史值；
- 或特定 fixture 的認證 evidence；

不得未經整理就升格成所有 Family、所有 topology 的 universal default。

## 11.4 WRAP delta

語意：

```text
在 WRAP Joint 指定的局部區域，保留合法包覆接觸並移除非法穿透
```

WRAP 可衍生：

- L 型 relief；
- 二級截角；
- 局部留肉；
- 局部 extra cut；
- face projection constraint。

但 WRAP 的方向與語意由 AssemblyJoint 決定，不由 Receiving module 私下定義。

---

# 12. Certified Relief Registry

## 12.1 Registry 是 runtime 製造真值

截角資料庫不是文件收藏，也不是 AI 提示詞。

它必須接在 runtime：

```text
基準檔/截角資料庫/certified_relief_rules.json
    ↓
ae_engine/certified_relief_registry.py
    ↓
lookup_certified_endcap_relief()
    ↓
manufacturing geometry
    ↓
2D / 3D / DXF
```

## 12.2 Registry HIT

只要 Registry HIT：

```text
Certified Rule = canonical manufacturing answer
```

Production code 不得另寫第二套公式。

3D solver 可以 shadow validation，但不能偷偷覆寫 certified formula。

## 12.3 Registry MISS

Registry MISS 才能進：

```text
3D discovery
candidate rule
shadow evidence
regression evidence
```

Candidate / provisional 不能冒充 certified。

## 12.4 每條 rule 必備語意

每條 Certified Rule 不能只剩：

```text
primary_u = ...
primary_v = ...
```

它必須保存：

```text
standard_ref
affected_zone
dimension_space
target_semantics
adjustment_type
adjustment_amount
topology_levels
formula
certification_evidence
revision
geometry_inputs
```

目的不是讓 JSON 變複雜，而是防止下一個 AI 看到 `OVERLAY` 後重新發明一套公式。

---

# 13. 展開 blank 與 BEND

## 13.1 blank 來源

blank W×H 只能來自每片 physical sheet 的 material segment chain。

正確：

```text
blank span = material segments sum
```

錯誤：

```text
blank span = final polygon bbox
blank span = 3D exploded preview bbox
blank span = 截角後外框最大最小值
```

## 13.2 BEND 來源

BEND positions 必須與 blank 共用同一份 material chain。

例：

```text
segments = 22 / 346 / 16
bend_1 = 22
bend_2 = 22 + 346 = 368
blank edge = 384
```

## 13.3 截角與孔不改 blank

截角、孔、局部挖料、止裂：

```text
會改 material polygon shape
會改 material area
不改 blank W×H
```

只有這些事件才會重算 blank：

```text
包外尺寸改變
Fold Topology 改變
physical piece 拆分方式改變
```

---

# 14. 2D / 3D / DXF / NC 的唯一資料來源

所有 consumer 都只能讀：

```text
Resolved Manufacturing Geometry
```

包含：

- 2D Preview；
- single-part 3D；
- assembly 3D；
- FinalScene；
- DXF；
- NC；
- batch output；
- collision solver；
- Save / Reload。

禁止各自：

- 從 `assembly_type` 再猜一次；
- 自己加減 `T`；
- 自己量 bbox；
- 自己決定 X Fold 存不存在；
- 自己重算 corner formula；
- 用 renderer 修正製造幾何。

---

# 15. 3D Solver 的權限

3D Solver 可以做：

- true-thickness solid 驗證；
- FACE_FLUSH 檢查；
- INSIDE_CLEARANCE 檢查；
- WRAP 合法接觸與非法穿透分離；
- 求解前 collision evidence；
- registry miss 的 discovery；
- candidate rule 的 shadow validation；
- 求解後 zero illegal penetration 驗證。

3D Solver 不可以做：

- 覆寫 STANDARD；
- 把 collision bbox 當正式截角公式；
- 把單一 fixture 數值升格成 universal rule；
- 改寫包外 / 料尺寸語意；
- 在 Registry HIT 時覆蓋 Certified Rule。

---

# 16. Receiving 已確認語意

## 16.1 後面板

Receiving 側背分離的後面板是完全平板：

```text
bend_count = 0
formed size = material size = blank size
```

不進 BA / BD / K-factor。

## 16.2 後面板寬度

已確認：

```text
BackPanelWidth = W - 2.5T
```

T=2、W=800：

```text
BackPanelWidth = 795
```

舊的 `W - 0.5T = 799` 不能作正式語意。

## 16.3 Receiving 操作員尺寸串

已確認：

```text
-24 / 24 / 29 / 350 / 800 / 350 / 29 / 18
```

這些是包外尺寸，不可直接塞進 material `len`。

要先依每段真實 fold topology 轉成料尺寸。

## 16.4 Receiving EndCap D

目前有一個必須處理的衝突：

```text
phase6-corner Skill 追加條款：Receiving EndCap D core = D - 2T
目前部分程式註解/實作曾出現：D - 3T
```

語意上，不能讓 caller 硬寫 `2T` 或 `3T`。

正確模式：

```text
Cabinet Family policy
    -> 回答 EndCap formed outside D
Fold Topology
    -> 回答 material core 應扣幾個 T
```

在正式修程式前，這一項應列為高優先 semantic/code/test mismatch，不能再靠舊測試互相覆蓋。

---

# 17. OVERLAY 與 formed FW 的最新定位

這裡要特別寫清楚，因為最容易混。

## 17.1 名義 FW

`FW = 25` 這類值是 EndCap 自己的材料 frame width。

它參與：

- EndCap 自己的 Y chain；
- STANDARD；
- 內邊框 / FW band；
- corner semantic delta。

## 17.2 formed FW occupation

箱身折好後在 mating face 上真正佔用的寬度，可以是：

```text
FW material + 相鄰 fold contribution
```

例如：

```text
25 + 2T = 29
```

它是 3D/裝配診斷的重要 evidence。

## 17.3 不可把 formed FW 寫回 EndCap FW

禁止：

```text
EndCap FW 25
因為 formed occupation 是 29
所以把 EndCap frame_width 改成 29
```

這會污染 Y 向截角與 EndCap 自身料鏈。

## 17.4 最新正式裁切語意

依目前最高優先整合語意與 registry v3：

```text
OVERLAY 上方 = STANDARD FW band 留肉 1T，使面齊
```

formed FW 可作 shadow evidence / diagnostic，不應重新變成脫離 STANDARD 的 CUTTING 公式核心。

---

# 18. X Fold Topology

在預設 Joint Map 下：

```text
INSERT:
  LEFT/RIGHT = INSERT
  X Fold 存在

OVERLAY:
  LEFT/RIGHT = OVERLAY
  X Fold 不存在

INSERT_OVERLAY:
  LEFT/RIGHT = INSERT
  X Fold 存在

包覆貼外:
  LEFT/RIGHT = INSERT
  BOTTOM = WRAP
  X Fold 存在
```

如果使用者 override 某一邊，實際 topology 由 resolved Joint + structure consequence 決定。

不能用 preset label 永遠硬推。

---

# 19. Save / Reload

Save / Reload 必須保存最終語意，而不是只保存舊 enum。

至少要保存：

```text
Assembly Intent preset
Resolved AssemblyJoint Graph
edge override
rule_id / revision
topology fingerprint
material segment chain
corner result / registry evidence
```

載入舊 `.p6fold` 時：

```text
若只有 assembly_type
    -> 可用 legacy migration 生成初始 Joint Graph
若已有明確 edge/corner override
    -> 優先保留具體資料
```

禁止 reload 後又用 `assembly_type` 把使用者改過的邊蓋回 default。

---

# 20. 舊值狀態分類

舊資料不能直接刪，也不能直接升格。

應標記：

```text
CONFIRMED_SEMANTIC
CONFIRMED_SEMANTIC_DEFAULT
CONFIRMED_FIXTURE
HISTORICAL_IMPLEMENTATION
LEGACY_DEFAULT
PROVISIONAL
DEPRECATED
```

範例：

```text
INSERT 固定 1T
status = HISTORICAL_IMPLEMENTATION 或 CONFIRMED_FIXTURE
```

```text
INSERT_OVERLAY 0.5T / 2T
status = HISTORICAL_IMPLEMENTATION 或 CONFIRMED_FIXTURE
```

只有有 evidence 後才能升為：

```text
CONFIRMED_SEMANTIC_DEFAULT
```

---

# 21. 目前 OPEN 項目

以下不得由下一個 AI 自行腦補：

1. `INSERT` 在 FW band 的正式 universal default 多切量。
2. `INSERT_OVERLAY` 的 `0.5T / 2T` 是否是所有 topology 的正式 default。
3. WRAP 在非既有 Receiving fixture 下的通用 reserve default。
4. 新 Family 的 target face / inside boundary 定義。
5. Receiving EndCap D compensation 在程式、Skill、test 間的正式收斂方式。
6. 舊 `phase6-overlay-relief-basis` Skill 中 `BOX_BODY_FORMED_FW` 公式要求，與最新 registry v3 STANDARD + 留肉語意的衝突修正。

---

# 22. 禁止再混用的概念

## 22.1 包外尺寸與 WRAP

錯：

```text
包外 18，所以是 WRAP
```

正：

```text
包外 18 是尺寸量法
WRAP 是 AssemblyJoint relation
```

## 22.2 16 與 18

錯：

```text
16 和 18 是兩種工法
```

正：

```text
16 = material dimension
18 = 同一段在 T=2 且相鄰一折時的 formed outside dimension
```

## 22.3 FW 25 與 FW 29

錯：

```text
25 和 29 是兩套 FW，可以互相覆蓋
```

正：

```text
25 = EndCap nominal/material FW
29 = 對應 folded occupation / formed outside evidence
```

## 22.4 assembly_type 與 Joint Graph

錯：

```text
assembly_type 決定所有角與所有邊
```

正：

```text
assembly_type / intent 只產生 default joint map
Resolved AssemblyJoint Graph 才是最終 truth
```

## 22.5 CornerType 與 AssemblyJoint

錯：

```text
Top CornerType 是全片組裝真值
```

正：

```text
Top CornerType 是局部截角投影 / legacy compatibility
AssemblyJoint Graph 是組裝真值
```

---

# 23. 實作前檢查清單

修改尺寸、Fold、Corner、Registry、3D、Assembly 前，必須逐項確認：

1. 這個數字是整體包外、板件成形包外，還是料尺寸？
2. 使用者沒說包外時，是否應按料尺寸理解？
3. 這段 material segment 當下有幾條相鄰真實 Fold？
4. Topology 是否因 Intent / Joint override 改變？
5. blank 是否只從 material chain 累加？
6. BEND positions 是否和 blank 用同一份 chain？
7. STANDARD 最內折線在哪裡？
8. Corner 附近有哪些 AssemblyJoint？
9. 每個 Joint 的 target face / inside boundary 是誰？
10. Semantic Delta 是留肉、多切、面齊、進內緣，還是 WRAP 包覆避讓？
11. Delta 的數值是否有 certified rule 或 evidence？
12. Registry HIT 時是否完全使用 registry formula？
13. Registry MISS 是否只進 candidate / shadow flow？
14. 2D / 3D / DXF / NC 是否讀同一份 resolved geometry？
15. Save / Reload 是否保存 resolved Joint，而不是重套 preset？

任一題答不出來：

```text
停止寫公式，先補語意或 evidence。
```

---

# 24. 最終不可破壞 Invariants

## Dimension

1. 整體包外、板件成形包外、料尺寸分層保存。
2. 料尺寸由當下真實 Fold Topology 換算。
3. blank W×H 由 material segment chain 得到。
4. BEND positions 與 blank 共用同一 chain。
5. 截角與孔不改 blank W×H。
6. 多片結構必須逐片展開。

## Assembly

7. Family 不重新定義 INSERT / OVERLAY / INSERT_OVERLAY / WRAP。
8. Intent 只是 preset。
9. AssemblyJoint Graph 是組裝 truth。
10. 同一片板可同時有多種 Joint。
11. WRAP 方向永遠是外側實體包覆內側實體。
12. OVERLAY 核心是 FACE_FLUSH。
13. INSERT 核心是 INSIDE_CLEARANCE。
14. resolved Joint 不得被 reload preset 覆蓋。

## Corner

15. STANDARD 永遠由最內實際 Fold line 定義。
16. Actual Corner = STANDARD + Semantic Delta。
17. 是否二級要看 final cutting topology，不看舊名稱。
18. 3D Solver 不得改寫 STANDARD。
19. Corner resolver 必須看 nearby Joint，不只看 assembly_type。

## Runtime

20. Registry HIT 是 canonical manufacturing answer。
21. Registry MISS 才進 3D discovery。
22. 2D / 3D / FinalScene / DXF / NC / Solver 共用 Resolved Manufacturing Geometry。
23. 新增任何 Intent / Joint relation 必須進 registry-driven regression matrix。

---

# 25. 給下一個 AI 的最短讀法

若只剩一分鐘，記住這段：

```text
Skill 決定 AI 怎麼改；截角資料庫決定程式算什麼。

尺寸先分三層：
整體包外、板件成形包外、料尺寸。

組合方式只是 preset：
最終真值是逐邊逐實體 AssemblyJoint Graph。

截角永遠是：
STANDARD + Semantic Delta。

STANDARD 只看真實 Fold Topology 的最內折線。

INSERT 是進內緣，多切量要 evidence。
OVERLAY 是面齊，依 STANDARD 留肉。
INSERT_OVERLAY 是局部 INSERT + OVERLAY hybrid。
WRAP 是外包內的 Joint relation，不是包外尺寸。

blank / BEND 只讀 material segment chain。
corner / hole 不改 blank W×H。

Registry HIT 禁止 production code 另寫第二套公式。
```

---

**END**
