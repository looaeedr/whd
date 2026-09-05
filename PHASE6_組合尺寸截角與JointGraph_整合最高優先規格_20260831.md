# PHASE6 組合、尺寸、標準截角與 AssemblyJoint Graph 整合最高優先規格

> **版本日期：2026-08-31**  
> **狀態：整合修正版／最高優先級機械語意規格**  
> **適用範圍：PHASE6 全 Cabinet Family、所有箱身結構、封頭、封尾，以及未來新增板件與組合方式**  
> **整合來源：**
> 1. `07_Phase6尺寸語意與標準截角母規則(2).md`（2026-08-30 已逐條確認，尺寸與 STANDARD 母規則優先級最高）
> 2. `組合類型語意規格_20260829(1).md`（Global Assembly Semantics、AssemblyJoint、WRAP 與 ownership 架構）
> 3. `補充(3).md`（2026-08-31 對「主面、四邊關係、組合方式只是預設」的補充定義）
>
> **本文件不是三份文件的摘要，而是將三份文件重新整合、修正衝突後形成的單一 Source of Truth。**

---

# 0. 文件優先序與衝突處理原則

## 0.1 優先序

若三份來源互相衝突，依下列順序處理：

1. **2026-08-30 尺寸語意與 STANDARD 母規則**優先於 2026-08-29 以前的固定數值與 dead formula。
2. **2026-08-29 AssemblyJoint / Joint Graph 補充**優先於早期「整片 EndCap 只有一個 assembly_type 就足夠」的模型。
3. **2026-08-31 主面與四邊關係補充**用來修正「組合方式」的理解：組合方式是常用高階 preset，不是四邊永遠不可改的絕對定義。
4. 舊程式、舊 registry、舊 regression 中已存在的固定數值，若未被新母規則重新確認，只能保留為：
   - historical implementation；
   - fixture；
   - evidence；
   - migration reference；
   不得自動升格成新的機械規格。

## 0.2 本次明確修掉的舊衝突

### 衝突 A：INSERT 預設多切量

舊文件曾把：

```text
INSERT
amount_t = 1.0T
```

寫成正式共用值。

**本整合版修正為：**

- INSERT 的母語意已確認：**進到對方內緣，需要相對 STANDARD 多切**。
- INSERT 作用在 STANDARD 的哪個區段已確認。
- **正式預設多切量尚未重新確認。**
- `1.0T` 若目前 production 中存在，只能標示為歷史 implementation / fixture，不得把它寫成機械母規則。

### 衝突 B：INSERT_OVERLAY 的 0.5T / 2T

舊文件曾把：

```text
secondary_retain_t = 0.5T
secondary_depth_t = 2T
```

寫成正式值。

**本整合版修正為：**

- `INSERT_OVERLAY` 的 hybrid 語意已確認。
- secondary step 必須由 STANDARD + 局部 INSERT + 局部 OVERLAY 解釋。
- `0.5T / 2T` 目前只能保留為歷史已存在值或既有認證 evidence。
- 在 production registry 重新宣告為正式 default 前，必須取得明確既有認證證據或再次確認。

### 衝突 C：「Top CornerType 是 Source of Truth」與「Joint Graph 是 Source of Truth」

兩句不能粗暴二選一，正確分層如下：

```text
全域最終機械 Source of Truth
= Canonical Dimension Model
+ Resolved AssemblyJoint Graph
+ STANDARD + Semantic Delta

Legacy / UI / EndCap 上方角投影
= Top CornerType
```

因此：

- `assembly_type` 不得反過來覆蓋已解析出的 Top CornerType。
- Top CornerType 仍是上方角的重要機械投影與 legacy compatibility truth。
- 但整片板件與所有邊的最終組裝真值，必須由 **AssemblyJoint Graph** 表達。

---

# 1. 一句話總結

PHASE6 最終不能再被建模成：

```text
選一個 assembly_type
    ↓
硬套一套截角公式
    ↓
2D 一套、3D 再猜一次
```

正確模型是：

```text
整體輸入尺寸
    ↓
Canonical Dimension Model
    ↓
Family / Structure Geometry
    ↓
Assembly Intent（高階常用預設）
    ↓
AssemblyJoint Graph（逐邊／逐實體真實接合）
    ↓
每個 Corner 收集附近 Joint
    ↓
STANDARD 固定母體
    +
Semantic Delta
    ↓
Resolved Manufacturing Geometry
    ↓
2D / 單板 3D / 組合 3D / FinalScene / DXF / NC / Solver / Save-Reload
```

最重要的三條 invariant：

> **Family 決定板件本身長什麼樣。**
>
> **AssemblyJoint 決定板件彼此怎麼接。**
>
> **STANDARD 永遠只由真實 Fold Topology 決定，任何工法只能從 STANDARD 做語意 delta。**

---

# 2. 名詞重新統一

## 2.1 包外尺寸（Outside Dimension）

「包外尺寸」是**尺寸量法**。

表示折彎成形後，以外側成形面量出的尺寸。

它不是任何組合方式。

禁止：

```text
看到「包外」
=> WRAP=True
```

## 2.2 料尺寸（Material Dimension）

板材展平後，某一條實際直線材料段的長度。

料尺寸與包外尺寸必須分欄保存。

## 2.3 板件成形包外尺寸（Part Formed Outside Dimension）

不是整台箱子的 W/H/D，也不是料尺寸。

它是「某一片實體板件組裝前，折完後自己應該有多大」。

例如：

```text
整體 D = 200
EndCap 成形主面包外 D = 198
EndCap 主面料 = 194（若上下兩端各有一條實際折彎、T=2）
```

這三層絕對不能混成一層。

## 2.4 OVERLAY — 貼外

`OVERLAY` 是 Assembly / Joint 語意。

核心不是「少一條折彎」。

核心是：

> **指定的局部成形面與 target face 面齊。**

## 2.5 INSERT — 嵌入

`INSERT` 的核心是：

> **指定局部成形區進入 target 的 inside boundary / mating zone。**

若 STANDARD 正好卡在內緣，仍需依工法多切出裝配間隙。

## 2.6 WRAP — 包覆 Joint

底層 `WRAP` 是**局部 AssemblyJoint relation**。

機械方向：

```text
外側實體
   ↓ 包覆
內側實體
```

注意：

- `WRAP` 不是包外尺寸。
- `WRAP` 不是 Receiving 專屬。
- `WRAP` 可以發生在上、下、左、右、前、後任何相鄰實體。
- Family 不能重新定義 WRAP 的方向。

## 2.7 主面

本專案對 EndCap / Tail 的討論中：

> **FW 所在的那一面定義為主面。**

我們口語上說「組合方式」時，多數是在描述**主面四周邊界，尤其上方兩角附近的預設 Joint 關係**。

## 2.8 組合方式不是絕對四邊鎖死

本次補充後，組合方式必須重新定義為：

> **一組常用的 Assembly Intent / Joint preset。**

它提供預設四邊關係，但不是不可更改的絕對限制。

真正精確的機械描述是：

> **哪一條邊，與哪一個鄰接實體，使用哪一種 Joint relation。**

---

# 3. 四層 Source of Truth

## 3.1 第一層：Canonical Dimension Model

負責：

- 整體輸入包外尺寸；
- 每片板件成形包外尺寸；
- 每一段 material dimension；
- 真實 Fold Topology；
- 展開 blank；
- BEND cumulative positions。

## 3.2 第二層：Family / Structure Geometry

Family 只回答：

- 板件有哪些；
- 一體／二件／三件；
- 側背是否分離；
- Fold Chain；
- 實際 Solid / Face；
- mating face 在哪裡；
- 實際座標、寬度、方向；
- Family 自己的產品 feature。

Family **不可以重新解釋 INSERT / OVERLAY / WRAP。**

## 3.3 第三層：Assembly Intent + AssemblyJoint Graph

### Assembly Intent

是操作員在 UI 選的高階常用方式。

它的作用：

```text
Intent
  ↓ expand
一組預設 AssemblyJoint
```

### AssemblyJoint

是實體對實體真正機械關係。

至少保存：

```text
subject_part
target_part
subject_face / region
target_face / mating_zone
edge / side
relation
direction
contact_mode
preserve_side
relief_intent
clearance_intent
solver_constraints
```

底層 `relation` 至少可表達：

```text
INSERT
OVERLAY
INSERT_OVERLAY（真正同一局部同時存在 outer contact + inner insertion 時）
WRAP
```

## 3.4 第四層：Resolved Manufacturing Geometry

由：

```text
Canonical Dimension
+
Family Geometry
+
AssemblyJoint Graph
+
STANDARD
+
Semantic Delta
```

合成唯一最終答案。

所有 consumer 只能讀這一層，不准再自己解釋組合方式。

---

# 4. 主面四邊 Joint 模型

為避免「一個 assembly_type 代表整片板」造成歧義，EndCap / Tail 主面至少要有：

```text
TOP
BOTTOM
LEFT
RIGHT
```

四邊關係。

每一邊可以指向不同 target part。

例如 Receiving 側背分離時：

```text
LEFT   -> 左側板
RIGHT  -> 右側板
BOTTOM -> 後面板或下方接合區
TOP    -> 箱身上方對應接合面
```

因此「同一塊 EndCap 同時有不同 Joint」是正常模型，不是例外。

---

# 5. 高階組合方式＝預設 Joint Map

## 5.1 INSERT — 嵌入

預設四邊：

```text
TOP    = INSERT
LEFT   = INSERT
RIGHT  = INSERT
BOTTOM = INSERT
```

語意：四邊預設都往對方內緣 / mating zone 進入。

注意：這是**預設**，不是禁止個別邊改成別的 Joint。

## 5.2 OVERLAY — 貼外

依本次補充定義，預設：

```text
TOP    = OVERLAY
LEFT   = OVERLAY
RIGHT  = OVERLAY
BOTTOM = INSERT
```

結果：

- 上方主面關係為面齊；
- 左右為貼外關係；
- 下方仍為嵌入；
- 左右 X Fold 在此預設下**物理上不存在**；
- 不是「有折邊但 UI 隱藏」。

## 5.3 INSERT_OVERLAY — 嵌入貼外

預設：

```text
TOP    = OVERLAY
LEFT   = INSERT
RIGHT  = INSERT
BOTTOM = INSERT
```

這個 preset 的上方角會同時遇到：

```text
TOP OVERLAY
+
SIDE INSERT
```

所以 Corner resolver 在上方角得到 hybrid：

```text
STANDARD
+
局部 OVERLAY（面齊 / 留肉）
+
局部 INSERT（進內緣 / 多切）
```

這才是 `INSERT_OVERLAY` 的真正機械來源。

禁止把名稱解釋成：

```text
左邊 INSERT
右邊 OVERLAY
```

## 5.4 包覆貼外 — 常用高階 preset

> **本整合版將常用「上貼外、左右嵌入、下方包覆」組合獨立列為高階 preset。**

其預設 Joint Map：

```text
TOP    = OVERLAY
LEFT   = INSERT
RIGHT  = INSERT
BOTTOM = WRAP
```

這個 preset 尤其符合 Receiving 常見接法，但**底層 relation 仍然全部是 Global AssemblyJoint，不是 Receiving 自己發明另一套語意。**

重要：

- 高階名稱「包覆貼外」不是底層 `WRAP` 的中文同義詞。
- 「包覆貼外」是一整組 preset；`WRAP` 是其中某一條邊的 Joint relation。
- 若右側也需要 WRAP，應直接把 `RIGHT` Joint 改成 WRAP；不需要再發明另一套硬編碼 Family 類型。
- 因此未來可以有多種 preset，但都只是 Joint Graph 的快捷模板。

## 5.5 預設與實際值的責任

```text
Assembly Intent preset
     ↓
產生 default Joint Map
     ↓
使用者／結構可合法調整個別 Joint
     ↓
Resolved Joint Graph = 最終真值
```

禁止：

```text
使用者改了一邊
但下一次 redraw 又用 assembly_type 把四邊全部重設
```

---

# 6. INSERT / OVERLAY / WRAP 的局部母語意

## 6.1 FACE_FLUSH（面齊）

典型：

- OVERLAY；
- 某些 WRAP 局部面。

定義：

```text
局部成形面 final position = target face
```

如果 STANDARD 下該區域太短：

```text
retain_delta = target - standard_formed_result
```

## 6.2 INSIDE_CLEARANCE（進內緣）

典型：INSERT。

定義：

```text
局部成形區 < target inside boundary
```

若 STANDARD 剛好在 boundary：

```text
相對 STANDARD 多切
```

正式 clearance / extra cut 必須由工法參數或認證規則提供，不能猜。

## 6.3 WRAP

WRAP 必須能回答：

```text
誰在外
誰在內
誰包誰
誰保留
誰避讓
contact face 是誰
哪個區域不得穿透
```

它可衍生：

- 局部留肉；
- 局部 extra cut；
- L 型 relief；
- 二級 corner；
- solver constraint。

---

# 7. 外高占用與箱身高度

已確認端部外高占用：

```text
INSERT          = 0T
OVERLAY         = 1T
INSERT_OVERLAY  = 1T
```

箱身成形高度：

```text
BoxBodyFinishedHeight
= H
- HeadOutsideOccupancy
- TailOutsideOccupancy
```

例：

| Head | Tail | 箱身成形高度 |
|---|---|---:|
| INSERT | INSERT | H |
| INSERT | OVERLAY | H-T |
| OVERLAY | INSERT | H-T |
| INSERT_OVERLAY | INSERT | H-T |
| OVERLAY | OVERLAY | H-2T |
| INSERT_OVERLAY | OVERLAY | H-2T |
| INSERT_OVERLAY | INSERT_OVERLAY | H-2T |

### WRAP 注意事項

WRAP 本身是局部 Joint。

**不得看到 WRAP 就固定加或扣 1T。**

若某個 WRAP 確實跨越整體外部端面而造成外高占用，必須由 resolved target face / end-plane projection 計算；不能從 relation 名稱硬推。

---

# 8. 尺寸三層模型

## 8.1 第一層：整體輸入包外尺寸

典型：

```text
W / H / D
```

例：

```text
W=400
H=500
D=200
T=2
```

代表整台箱組裝完成後的包外目標。

## 8.2 第二層：各 physical piece 成形包外尺寸

組合與 Family Geometry 先決定每片板件折完後應該多大。

例：

```text
整體 D = 200
箱身成形包外 D = 200
EndCap 成形主面包外 D = 198
```

## 8.3 第三層：material segment dimension

通則：

```text
料尺寸
= 包外尺寸
-（該 material segment 當下真正相鄰的折彎數 × T）
```

相鄰折彎數：

```text
0 bend -> -0T
1 bend -> -1T
2 bend -> -2T
```

**Topology 變，料尺寸就必須重算。**

---

# 9. 對話與 UI 尺寸解讀規則

## 9.1 UI 的 W/H/D/FW

操作員 GUI 層看到的 W/H/D/FW 等整體／成形欄位，依本專案約定是**包外尺寸**。

## 9.2 製造討論中的「折 15」「FW 25」

若使用者沒有特別說「包外」，先按**料尺寸**理解。

T=2 例：

```text
料 15 + 1 個相鄰折彎 -> 包外 17
料 16 + 1 個相鄰折彎 -> 包外 18
料 25 + 左右各 1 個折彎 -> 包外 29
```

## 9.3 正負號

```text
-24
```

只表示 bend orientation。

```text
尺寸大小 = 24
方向 = negative orientation
material length = 正 24 對應的換算結果
```

負號不能參與料長加減。

---

# 10. 展開 blank 與 BEND 線只能共用同一份料鏈

每一方向：

```text
blank span = material segments 直接累加
```

BEND position：

```text
bend_i = 前面 material segments cumulative sum
```

例：

```text
segments = 22 / 346 / 16
```

得到：

```text
bend_1 = 22
bend_2 = 22 + 346 = 368
blank edge = 384
```

禁止：

- UI 算一次 blank；
- 2D 再算一次 bend；
- 3D 用 bbox 反推；
- Assembly 再自己量一次。

---

# 11. 截角與孔不改 blank W×H

若原始 blank：

```text
400 × 500
```

角落切掉 15×15，blank 仍然是：

```text
400 × 500
```

截角、孔洞、止裂、局部挖料：

- 改 polygon shape；
- 改 material area；
- **不改 segment chain 得到的 blank W×H。**

只有以下事件才重算 blank：

1. 包外 segment 改變；
2. Fold Topology 改變；
3. physical piece 拆分方式改變。

---

# 12. 二件式／三件式必須逐片展開

禁止：

```text
先算整體箱身 blank
再把結果切兩片／三片
```

每片 physical sheet 都必須自己走完整鏈：

```text
part formed outside segments
-> real fold topology
-> material segments
-> bend cumulative positions
-> blank W×H
```

至少保存：

### 二件式

```text
左箱身 blank
右箱身 blank
```

### 三件式 W 分割

```text
左片 blank
中片 blank
右片 blank
```

### 三件式側背分離

```text
左側板 blank
後面板 blank
右側板 blank
```

再加：

```text
Head blank
Tail blank
Door blank
Base blank
Indicator blank
其他每片實體 blank
```

---

# 13. Receiving 後面板

## 13.1 完全平板

Receiving 側背分離的後面板：

> **完全沒有折彎。**

所以：

```text
bend_count = 0
formed size = material size = blank size
```

不進 BA / BD / K-factor。

## 13.2 後面板寬度

正式已確認：

```text
BackPanelWidth
= W - T - T - 0.5T
= W - 2.5T
```

例：

```text
W=800
T=2
BackPanelWidth=795
```

舊：

```text
W - 0.5T = 799
```

已判定錯誤，不得作正式 Source of Truth。

## 13.3 後面板高度

```text
BackPanelHeight
= H
- HeadOutsideOccupancy
- TailOutsideOccupancy
```

T=2、H=1600 例：

```text
INSERT + INSERT = 1600
OVERLAY + INSERT = 1598
INSERT + OVERLAY = 1598
OVERLAY + OVERLAY = 1596
INSERT_OVERLAY + INSERT = 1598
INSERT_OVERLAY + INSERT_OVERLAY = 1596
```

---

# 14. EndCap / Tail Y 方向完整尺寸鏈

例：

```text
D=200
T=2
```

Y 向 physical roles：

| 現有名稱 | 物理角色 |
|---|---|
| ytop1 | 內邊框／放門 |
| FW | 邊框 |
| D 主面 | 箱體深度主面 |
| ybottom1 | 與箱身接觸／焊接折邊 |

已確認：

```text
ytop1 料 = 16，包外 = 18
FW     料 = 25，包外 = 29
D 主面成形包外 = 198
D 主面料 = 198 - 2T = 194
ybottom1 料 = 15，包外 = 17
```

所以：

```text
Y blank
= 16 + 25 + 194 + 15
= 250
```

BEND positions 也只能從這份料鏈累加。

---

# 15. EndCap / Tail X 方向 INSERT 基準

例：

```text
W=400
T=2
```

左右焊接折：

```text
料 = 15
包外 = 17（單一相鄰折彎）
```

INSERT 下：

```text
EndCap X 主面成形包外
= W - 2T
= 396
```

主面左右都有 Fold 時：

```text
X 主面料
= 396 - 2T
= 392
```

所以：

```text
X blank
= 15 + 392 + 15
= 422
```

---

# 16. OVERLAY X 向：兩層 +2T 必須分開

不能簡寫成：

```text
OVERLAY 沒有 X Fold
所以 blank / formed X 直接等於 W
```

正確語意鏈：

```text
392 material baseline
-> +2T（原本左右 Fold 對包外尺寸的補償）
-> 396 formed baseline
-> +2T（OVERLAY 面齊到箱身外框）
-> 400 flush result
```

這兩個 `+2T` 意義完全不同：

1. 第一個是 material -> formed outside 的 Fold 補償；
2. 第二個是 Assembly 的 FACE_FLUSH 語意。

即使最後數值碰巧等於 W，也不准把中間語意刪掉。

---

# 17. STANDARD：所有截角唯一母體

## 17.1 固定不變

```text
ActualCorner
= STANDARD
+ Semantic Delta
```

禁止：

```text
INSERT 一套 dead formula
OVERLAY 一套 dead formula
INSERT_OVERLAY 一套 dead formula
WRAP 一套 dead formula
```

## 17.2 STANDARD 幾何定義

> **從材料外緣，截到該方向最內部的實際折彎線。**

不是：

- 第一條折彎線；
- 某個 CornerType 固定答案；
- solver collision bbox；
- Family 自己的 magic number。

## 17.3 Fold Topology 改變時

STANDARD 本身的**規則不變**，但因實際最內部折彎線變了，重新依新 topology 求幾何。

這不叫「改 STANDARD 規則」。

---

# 18. STANDARD 數值範例

沿用：

```text
X 側折料 = 15
內邊框料 = 16
FW 料 = 25
D 主面料 = 194
下折料 = 15
```

## 18.1 上方 STANDARD

Y 最內折線：

```text
16 + 25 = 41
```

所以：

```text
上方 STANDARD = 15 × 41
```

## 18.2 下方 STANDARD

```text
下方 STANDARD = 15 × 15
```

## 18.3 不同 X band 的成形狀態

Y blank：

```text
250
```

### X = 0~15

上下相關 Fold 都被 STANDARD 切掉：

```text
formed outside state = 194
```

### X = 15~40

```text
40 = 15 + FW料25
```

上 Fold 被切掉，下 Fold 還在：

```text
194 + 1T = 196
```

### X > 40

上下 Fold 都在：

```text
194 + 2T = 198
```

因此：

```text
194 -> 196 -> 198
```

是同一份 STANDARD + 真實 Fold Topology 的自然分區，不是三套公式。

---

# 19. OVERLAY 上方 Corner 語意

STANDARD 在 FW band 為：

```text
196
```

目標正常主面：

```text
198
```

所以面齊：

```text
retain = 198 - 196 = 1T
```

也就是：

```text
OVERLAY
= STANDARD
+ FW band 留肉 1T（在這個已確認 fixture 下）
```

### 下方不自動跟著留

上方 OVERLAY 的 target 是上方局部面。

所以：

```text
下方 STANDARD 15×15
```

維持不變。

禁止：

```text
OVERLAY => 上下都留 1T
```

留不留必須看該局部 region 是否需要 FACE_FLUSH。

---

# 20. INSERT 上方 Corner 語意

箱身內緣 fixture：

```text
196
```

STANDARD 在 FW band 也是：

```text
196
```

INSERT 要真的能進入：

```text
final formed state < 196
```

所以需要相對 STANDARD 多切。

但：

> **正式預設多切量目前未重新確認。**

禁止自動宣告：

```text
0.5T
1T
其他歷史值
```

為新標準。

另外：

> **INSERT 有 extra cut 不等於二級截角。**

只有實際 cutting polygon 出現第二個 step / band / L shape 才叫二級。

---

# 21. INSERT_OVERLAY 上方 Corner 語意

它的核心：

```text
STANDARD
+
局部 INSERT：進內緣 -> 多切
+
局部 OVERLAY：面齊 -> 留肉
```

在高階 preset 的 default Joint Map 中，上角正好由：

```text
TOP = OVERLAY
SIDE = INSERT
```

共同形成 hybrid corner。

### 重要修正

以下歷史值：

```text
secondary_retain_t = 0.5T
secondary_depth_t = 2T
```

可以保留為歷史 fixture / evidence，但本整合版**不宣告為最新正式母規則**。

production registry 要正式採用前，必須：

1. 由 STANDARD band 解釋它；
2. 說清楚 retain/depth 各作用在哪個區域；
3. 有認證 evidence 或明確確認。

---

# 22. 二級截角的唯一正確定義

二級截角不是「有某個參數」。

下列都不能單獨證明二級：

- 有 `secondary_retain_t`；
- 有 0.5T；
- 有 FW；
- 有 extra cut；
- 有 INSERT；
- 有 INSERT_OVERLAY 名稱。

唯一判定：

> **最終實際 CUTTING 幾何真的出現第二個階梯、第二個 band、L shape 或第二個獨立切除區。**

---

# 23. WRAP / 包覆下方 Corner

## 23.1 下方 STANDARD 不變

```text
STANDARD = 15 × 15
```

WRAP 只能從它衍生。

## 23.2 已確認 L 型 fixture

當：

```text
側折料 = 15
側板後折料 = 15
下折料 = 15
X 預留 = 2
Y 預留 = 1
```

得到：

```text
Primary U = 15 + 15 - 2 = 28
Primary V = 15 - 1 = 14
Secondary U = 15
Secondary depth = 1
```

即：

```text
28×14 + 15×1
```

正確解釋：

```text
STANDARD 15×15
-> 因 WRAP 要與 target side formed face 包覆／面齊
-> 沿側板後折方向延伸 relief
-> 保留 X/Y 指定預留
-> 形成 L 型二級衍生角
```

**28×14 + 15×1 不是 STANDARD。**

## 23.3 WRAP 不得 Family hard-code

錯：

```text
if Receiving:
    用 WRAP 28×14 + 15×1
```

正：

```text
Resolved mating geometry
+
WRAP semantic
+
clearance / preserve params
+
STANDARD
-> final corner
```

---

# 24. Corner Resolver 必須看附近 Joint

每個 Corner：

```text
Corner
  ↓
Collect nearby AssemblyJoints
  ↓
取得各 Joint 的 relation / target / direction
  ↓
取得 STANDARD
  ↓
Resolve semantic deltas
  ↓
合成 final cutting polygon
```

例如：

```text
對側板 = INSERT
對上方主面 = OVERLAY
```

上角就得到 INSERT_OVERLAY hybrid。

又例如：

```text
對側板 = INSERT
對後板 = WRAP
```

下角就不能只看整片 `assembly_type`。

---

# 25. Corner Registry 應保存語意，不只保存答案

認證規則至少必須保存：

```text
rule_id
revision
family_scope（若只是幾何 fixture，不能改 relation 語意）
subject_part
target_part
edge / corner
STANDARD reference
semantic relation
semantic target
active band / segment
retain_delta
extra_cut_delta
clearance
secondary topology definition
user_adjustable parameters
evidence
fixture values
```

語意 target 建議至少能表達：

```text
FACE_FLUSH
INSIDE_CLEARANCE
RETAIN
EXTRA_CUT
WRAP
```

禁止 registry 只存：

```text
40×23
29×39
28×14
```

這些只可作 fixture expected result。

---

# 26. Canonical blank 必須資料化

每一片 physical sheet 必須保存等價資訊：

```yaml
unfolded_blank:
  width:
  height:
  source_revision:
  segment_chain_x:
  segment_chain_y:
  bend_positions_x:
  bend_positions_y:
  formed_dimensions_reference:
  topology_fingerprint:
```

每個 segment 至少：

```yaml
name:
physical_role:
outside_dimension:
material_dimension:
bend_count_before:
bend_count_after:
bend_direction:
source:
```

完全平板：

```text
bend_count=0
formed=material=blank
```

---

# 27. Save / Reload Source of Truth

`.p6fold` 或等價儲存格式至少要能還原：

1. 整體 input outside dimensions；
2. 每片 physical piece 的 formed dimensions；
3. material segment chains；
4. real Fold Topology；
5. blank W×H；
6. bend positions；
7. Assembly Intent（UI 摘要／preset 名稱）；
8. Resolved AssemblyJoint Graph；
9. Corner semantic selections / user overrides；
10. topology fingerprint；
11. rule revision。

### 禁止 Save/Load 後重新套 preset 覆蓋實際 Joint

錯：

```text
load assembly_type
-> apply defaults
-> 把已儲存的 RIGHT WRAP 改回 INSERT
```

正：

```text
load resolved joints
-> intent 只作摘要／UI mirror
-> 缺舊資料時才做 legacy migration
```

---

# 28. assembly_type / Top CornerType / Joint Graph 的最終責任

## 28.1 `assembly_type`

只可作：

- UI preset；
- UI label；
- 快捷套用；
- 儲存摘要；
- legacy compatibility fallback。

不得作最終唯一機械真值。

## 28.2 Top CornerType

是：

- 上方 Corner 的 resolved mechanical projection；
- legacy 路徑的重要機械真值；
- 不得被 `assembly_type` 載入時任意覆蓋。

但它也不是整片 EndCap 所有邊的完整 Joint Graph。

## 28.3 AssemblyJoint Graph

最終回答：

```text
誰跟誰接
哪一邊接
誰外誰內
誰貼誰
誰插誰
誰包誰
target face 是誰
需不需要 preserve / relief / clearance
```

所以全域 final assembly SoT = Joint Graph。

---

# 29. Global Assembly Semantics 擁有什麼

Global 層擁有：

- Assembly Intent Registry；
- AssemblyJoint Registry；
- INSERT；
- OVERLAY；
- INSERT_OVERLAY hybrid relation；
- WRAP；
- inside / outside；
- outer contact；
- inner insertion；
- who wraps whom；
- FACE_FLUSH；
- INSIDE_CLEARANCE；
- occupancy semantic；
- fold existence semantic；
- mating relation；
- preserve / relief / clearance intent；
- Assembly-derived Corner policy；
- solver constraints；
- Intent -> default Joint Map。

---

# 30. Family Geometry 擁有什麼

Family 只擁有：

- W/H/D/T 的產品 default；
- 板件數量；
- 一體／二件／三件；
- 側背分離；
- Fold Chain；
- 實際 Solid / Face；
- mating zone 的實際座標；
- effective mating width；
- Family-specific structural geometry；
- 孔、門、底板、指示燈盒等 feature。

禁止 Family 擁有：

```text
INSERT 在我這裡意思不同
OVERLAY 在我這裡仍有 X Fold
WRAP 在我這裡方向相反
受電箱下角自己另定 assembly policy
```

---

# 31. Receiving effective mating width 的正確 ownership

如果 Receiving 由實際幾何得到：

```text
bottom_effective_mating_width
= side_rear_bend + T
```

可以保留「這個數值結果」。

但 ownership 應寫成：

```text
Receiving Structure Geometry
    ↓
Resolved mating face
    ↓
effective_mating_width
    ↓
Global Joint / Corner policy 使用
```

不能寫成：

```text
Receiving 自己的 INSERT_OVERLAY 定義
```

---

# 32. 2D / 3D / DXF / NC / Solver 共用資料鏈

所有 consumer：

```text
2D
single-part 3D
assembly 3D
FinalScene
DXF
NC
batch output
collision solver
interference solver
```

全部只能讀：

```text
Resolved Manufacturing Geometry
```

禁止各自：

- 再從 `assembly_type` 猜一次；
- 再加 T；
- 再量 bbox；
- 再建立自己的 corner formula；
- 再決定 X Fold 存不存在。

---

# 33. 3D Solver 的權限

3D Solver 可以：

- 驗證 FACE_FLUSH；
- 驗證 INSIDE_CLEARANCE；
- 找未知 relation 的 provisional evidence；
- 顯示求解前干涉；
- 求解 relief / cutback；
- 驗證零非法穿透。

3D Solver 不可以：

- 覆蓋 STANDARD；
- 看到 collision bbox 就改 CornerType 母規則；
- 把 fixture 尺寸升格成 universal formula；
- 重新解釋包外／料尺寸。

求解順序：

```text
1. 每片板先依自己的 Fold / Corner / Feature 建真實 formed solid
2. 建立 AssemblyJoint Graph
3. resolve outside/inside/wrap/insert/overlay
4. 求解需要的 relief / cutback
5. 驗證 final solid zero penetration
```

---

# 34. X Fold Topology 規則

在 default preset 下：

## INSERT

```text
LEFT = INSERT
RIGHT = INSERT
=> X Fold 存在
```

## OVERLAY

```text
LEFT = OVERLAY
RIGHT = OVERLAY
=> X Fold 不存在
```

所以必須同步：

- 2D 無 X BEND；
- 3D 無側折面；
- Fold Editor 不列不存在折彎；
- blank segment chain 依 flat topology 重算；
- 切回 folded preset 才恢復。

## INSERT_OVERLAY

```text
LEFT = INSERT
RIGHT = INSERT
=> X Fold 存在
```

## 包覆貼外 preset

預設：

```text
LEFT = INSERT
RIGHT = INSERT
=> X Fold 存在
BOTTOM = WRAP
```

若使用者把 RIGHT 改成 WRAP 或 OVERLAY，實際 topology 應由該 Joint 的 resolved structural consequence 決定，不得仍死跟 preset label。

---

# 35. 目前程式架構需要收斂的地方

## 35.1 移除 Family-specific assembly-derived bottom policy ownership

例如 Receiving module 不應自己決定：

```text
bottom CornerType
amount_t
secondary_retain_t
secondary_depth_t
```

若這些是 assembly / mating relation 衍生，就應搬到 shared resolver。

## 35.2 移除 Shared policy + Family policy 雙 ownership

同一個下方角不能同時有：

```text
shared default
+
receiving override
```

否則必然造成：

- 2D 一套；
- 3D 一套；
- 換 Family 一套；
- Save/Load 又一套。

## 35.3 Intent preset 與 actual Joint 分離

需要明確 API 概念：

```text
apply_intent_preset()
resolve_joint_graph()
resolve_corner_from_nearby_joints()
```

而不是一個 `apply_box_assembly_type()` 同時修改所有層。

---

# 36. 建議資料結構

以下是語意要求，不強迫實作名稱完全一致。

## 36.1 AssemblyIntent

```yaml
intent_id:
display_name:
default_joint_map:
  TOP:
  BOTTOM:
  LEFT:
  RIGHT:
revision:
```

## 36.2 AssemblyJoint

```yaml
joint_id:
subject_part:
target_part:
subject_region:
target_region:
edge:
relation:
direction:
contact_mode:
preserve_side:
clearance:
relief_intent:
solver_constraints:
source: preset | user_override | migration | solver_confirmed
revision:
```

## 36.3 ResolvedCorner

```yaml
corner_id:
standard_geometry:
nearby_joint_ids:
semantic_deltas:
final_cut_geometry:
topology_level:
evidence:
revision:
```

## 36.4 ResolvedPieceGeometry

```yaml
part_id:
formed_dimensions:
segment_chain_x:
segment_chain_y:
bend_positions:
unfolded_blank:
fold_topology:
corner_geometries:
feature_geometries:
assembly_joints:
topology_fingerprint:
```

---

# 37. 預設 Joint Map 對照表

| 高階 Intent / preset | TOP | LEFT | RIGHT | BOTTOM | 預設 X Fold | 備註 |
|---|---|---|---|---|---|---|
| 嵌入 INSERT | INSERT | INSERT | INSERT | INSERT | 有 | 四邊預設嵌入 |
| 貼外 OVERLAY | OVERLAY | OVERLAY | OVERLAY | INSERT | 無 | 左右貼外導致 X Fold 不存在 |
| 嵌入貼外 INSERT_OVERLAY | OVERLAY | INSERT | INSERT | INSERT | 有 | 上角由 TOP OVERLAY + SIDE INSERT 形成 hybrid |
| 包覆貼外 | OVERLAY | INSERT | INSERT | WRAP | 有 | 常用 Receiving preset，但語意仍全域 |

注意：

> 表格只是 default preset；Resolved Joint Graph 可以合法出現不同 edge override。

---

# 38. 高階 Intent 與 CornerType 不得一對一硬綁

過去容易寫成：

```text
assembly_type = X
=> 4 個角都套固定 CornerType
```

現在必須改為：

```text
Intent
-> default edges
-> nearby Joint combination
-> Corner semantic classification
-> STANDARD + delta
```

例如 `INSERT_OVERLAY` 上角才是 hybrid；下角若 TOP 不參與，就不能因 Intent 名稱而強迫套上同一個 secondary corner。

---

# 39. Default 不是 Absolute

這是本次補充的核心。

任何文件、UI、程式都必須把下列兩種狀態分開：

```text
DEFAULT
RESOLVED / USER OVERRIDDEN
```

預設只是：

- 常用初始值；
- 快速操作；
- 新板件初始化。

不代表：

- 使用者不能改；
- solver 不能根據真正 target face 求實際 delta；
- reload 時可以重新覆蓋；
- 所有 Family 永遠四邊完全相同。

---

# 40. Registry 自動回歸矩陣

回歸不能手工白名單只寫：

```text
INSERT
OVERLAY
INSERT_OVERLAY
```

應從 registry 自動取：

```text
all AssemblyIntent
all AssemblyJoint relation
all supported Family
all supported Structure
```

建立參數化矩陣。

至少包含：

## 40.1 Intent 基本矩陣

- INSERT；
- OVERLAY；
- INSERT_OVERLAY；
- 包覆貼外；
- future intents 自動加入。

## 40.2 Head / Tail

每一 Intent：

- Head；
- Tail；
- Head/Tail 不同組合；
- Tail mirror orientation。

## 40.3 Edge overrides

至少測：

- RIGHT 改 WRAP；
- LEFT / RIGHT 不同 relation；
- BOTTOM WRAP；
- TOP OVERLAY + SIDE INSERT hybrid。

## 40.4 Family

- 金庫型；
- 受電箱；
- future Family 自動加入。

Family 差異只允許出現在：

- resolved face；
- actual coordinate；
- effective mating dimension；
- structural pieces。

同一 relation 的語意 fields 必須一致。

---

# 41. 幾何回歸必測項

每個 case 至少驗證：

1. canonical formed dimensions；
2. material segment lengths；
3. Fold Topology；
4. blank W×H；
5. BEND positions；
6. STANDARD corner；
7. semantic delta；
8. final cutting polygon；
9. 2D corner / fold / hole；
10. single-part 3D；
11. assembly 3D；
12. FinalScene；
13. 求解前 collision candidates；
14. 求解後 zero illegal penetration；
15. Save / Reload；
16. DXF；
17. NC；
18. batch output；
19. topology fingerprint 一致。

---

# 42. 2D / 3D 一致性硬規則

以下視為阻斷性交付 Bug：

- 2D 有 Fold、3D 沒 Fold；
- 2D 無 Fold、3D 還折出側面；
- 2D corner 38×27、3D 40×27；
- 2D blank 與 3D 展開尺寸不同；
- assembly 3D 自己量 bbox 得另一個尺寸；
- Save/Load 後 CornerType 被 assembly_type 蓋掉；
- 同一 Joint 在 Family 切換後 relation 改義。

---

# 43. 不准再犯的尺寸錯誤

## 43.1 包外 18 ≠ WRAP

```text
包外 18 = 尺寸層
WRAP = Joint 層
```

## 43.2 16 / 18 不是兩種工法

T=2：

```text
16 = material
18 = same segment formed outside
```

## 43.3 FW 25 / 29 不是兩套 FW

```text
FW material = 25
兩側各一折、T=2
formed outside = 29
```

## 43.4 W/H/D 不等於每片料

```text
D=200
-> EndCap formed outside=198
-> material=194（對應 topology）
```

## 43.5 截角後 bbox 不等於 blank

blank 只能從 segment chain 得到。

---

# 44. 不准再犯的 Corner 錯誤

## 44.1 STANDARD 截第一折

錯。

STANDARD 截最內部折彎線。

## 44.2 把 41 叫 FW

錯。

```text
16 = 內邊框料
25 = FW料
41 = cumulative standard depth
```

## 44.3 INSERT extra cut = 二級

錯。

## 44.4 0.5T = 二級定義

錯。

## 44.5 solver bbox 覆蓋 STANDARD

錯。

## 44.6 上方 OVERLAY 留肉 => 下方一起留

錯。

Semantic delta 必須看 target face。

---

# 45. 不准再犯的 Assembly 錯誤

## 45.1 Family 重新解釋 relation

錯：

```text
Receiving 的 INSERT_OVERLAY 跟 Vault 不同
```

正：

```text
relation 意義相同
Family 只提供不同 target face
```

## 45.2 OVERLAY 還保留 X Fold

錯。

在 OVERLAY 預設中左右 Joint=OVERLAY，所以 X Fold 不存在。

## 45.3 只存一個 assembly_type

不夠。

必須能保存逐邊／逐實體 Joint。

## 45.4 WRAP 寫在 Receiving module

錯。

WRAP 是 Global AssemblyJoint。

## 45.5 下方 CornerType 反推出整片組合方式

錯。

Corner 是局部加工結果；Joint Graph 才是 assembly truth。

---

# 46. 實作前強制檢查清單

修改尺寸、Fold、Corner、Registry、3D、Assembly 前，必須逐題回答：

1. 這個數字是整體包外、板件成形包外、還是 material？
2. 使用者沒說包外時，是否應按料尺寸理解？
3. 此 material segment 當下左右各有幾條真實 Fold？
4. 包外轉料應扣幾個 T？
5. blank 是否只由 material chain 累加？
6. BEND positions 是否與 blank 用同一份 chain？
7. STANDARD 最內折線在哪？
8. Corner 附近有哪些 AssemblyJoint？
9. 每個 Joint 的 target face / inside boundary 是誰？
10. 語意是 FACE_FLUSH、INSIDE_CLEARANCE、WRAP、RETAIN 還是 EXTRA_CUT？
11. delta 作用在哪一個 band？
12. delta 是否有正式認證值？
13. 最終 geometry 是否真的形成 secondary step？
14. 這片是單片、二件、三件中的哪一 physical sheet？
15. Save / Reload 是否保存 resolved Joint，而不是重套 preset？
16. 2D / 3D / DXF / NC 是否只讀 resolved result？
17. solver 是否只驗證／求解，而沒有改寫 STANDARD？

答不出來：

> **停止寫 dead formula，不得猜。**

---

# 47. 本次整合後仍未正式確認的數值

以下項目明確列為 OPEN，不得擅自補：

1. **INSERT 在 FW band 的正式預設多切量。**
2. **INSERT_OVERLAY 每一個 secondary retain / depth 是否正式沿用歷史 0.5T / 2T。**
3. 新 Family 的 target face / inside boundary 尚未建立時，其實際 relation geometry。
4. WRAP 在非既有 15/15/2/1 fixture 下的通用 adjustable default，必須由 semantic parameter 定義，不得只比例猜。
5. 「包覆貼外」若未來需要正式 internal enum / ID，ID 名稱應由實作層統一決定；本文件只固定中文顯示名稱與 Joint Map 語意。

---

# 48. 舊值保留方式

舊資料不得直接刪光，應標示 status：

```text
CONFIRMED_SEMANTIC
CONFIRMED_FIXTURE
HISTORICAL_IMPLEMENTATION
LEGACY_DEFAULT
PROVISIONAL
DEPRECATED
```

例：

```text
INSERT secondary? 1T
status = HISTORICAL_IMPLEMENTATION
```

```text
INSERT_OVERLAY 0.5T / 2T
status = HISTORICAL_IMPLEMENTATION 或 CONFIRMED_FIXTURE
```

直到有 evidence 才能升為：

```text
CONFIRMED_SEMANTIC_DEFAULT
```

---

# 49. 建議 migration 順序

1. 建立 canonical dimension model；
2. 把 material / outside 分欄；
3. 將 Assembly Intent 與 Joint Graph 分開；
4. 建立 Intent -> default Joint Map；
5. 新增「包覆貼外」preset；
6. 將 WRAP 放入全域 Joint Registry；
7. 將 Corner resolver 改成附近 Joint + STANDARD；
8. 移除 Receiving 對 assembly-derived bottom policy 的 ownership；
9. 將 Top CornerType 改成 resolved projection，不讓 assembly_type 反蓋；
10. 將 blank / bend positions 資料化；
11. 2D / 3D / DXF / NC / Solver 全改讀 resolved geometry；
12. Save/Load 優先保存 Joint Graph；
13. 舊 `.p6fold` 無 Joint Graph 時做單次 legacy migration；
14. 加 registry-driven regression matrix；
15. 全部通過才允許打包交付。

---

# 50. Legacy migration 原則

舊檔若只有：

```text
assembly_type = INSERT_OVERLAY
```

可用當時版本的 preset 生成初始 Joint Graph：

```text
TOP=OVERLAY
LEFT=INSERT
RIGHT=INSERT
BOTTOM=INSERT
```

但要標記：

```text
source = legacy_migration
```

如果舊檔已有明確 CornerType / edge override，migration 必須優先保留那些具體資料，不能拿 assembly_type 再蓋掉。

---

# 51. 「包覆貼外」preset 的最終定位

本次整合後，這個常用組合不再被寫成：

```text
Receiving 特殊 if
```

而是：

```text
Global Assembly Intent preset：包覆貼外

TOP    OVERLAY
LEFT   INSERT
RIGHT  INSERT
BOTTOM WRAP
```

Receiving 只是目前最常用這個 preset 的 Family 之一。

如果未來 Vault 或其他 Family 也有相同 Joint Map，可以直接共用。

如果某個 Family 的實際 target face 不同，只改 Family Geometry mapping，不改 relation 意義。

---

# 52. 為什麼這樣可以同時保留「組合類型」與「逐邊 Joint」

不需要把組合類型整個刪掉。

組合類型對操作員仍非常有價值：

- 一次套四邊常用值；
- UI 易懂；
- 檔案摘要；
- 報表名稱；
- 常用工法選擇。

但是程式內部不能因此偷懶成：

```text
一個 enum 決定所有 corner
```

正確：

```text
高階 Intent 保留
+
底層 Joint Graph 精確化
```

---

# 53. 最終對照：舊理解 vs 新整合規格

| 舊理解 | 新整合規格 |
|---|---|
| assembly_type 就是整片板的真相 | assembly_type 是高階 preset；Joint Graph 是全域組裝真值 |
| 組合方式四邊永遠固定 | 四邊只是 preset default，可有合法 override |
| Receiving 可以自訂 INSERT_OVERLAY 意義 | 不行，relation 全域同義；Family 只映射實際 face |
| WRAP 是 Receiving 下方特殊開關 | WRAP 是 Global AssemblyJoint，可發生任意相鄰實體 |
| 看到 WRAP 就改 15→18/19 | 錯；那是 material/outside 尺寸層 |
| 每種 CornerType 各有 dead formula | 全部 STANDARD + Semantic Delta |
| INSERT=固定 1T | 多切語意確認，正式 default 尚未重新確認 |
| INSERT_OVERLAY=固定 0.5T/2T | hybrid 語意確認；該數值暫列歷史 evidence |
| solver 算多少就是規格 | solver 驗證／求解，不得覆蓋 STANDARD |
| 2D/3D 各算一次 | 全部只讀 Resolved Manufacturing Geometry |
| 展開尺寸由 bbox | blank 由 material segment chain |

---

# 54. 最終不可破壞的 Invariants

## Dimension Invariants

1. 包外尺寸、板件成形包外、material dimension 分層。
2. material 只依當下真實 Fold Topology 換算。
3. blank = material segments sum。
4. bend positions = 同一 material chain cumulative sum。
5. corner / hole 不改 blank W×H。
6. 多片結構逐片計算。

## Assembly Invariants

7. Family 不重新定義 INSERT / OVERLAY / WRAP。
8. Intent 只是 preset。
9. Joint Graph 才能完整描述整片板。
10. 同一片板可同時有多種 Joint。
11. WRAP 方向永遠外包內。
12. OVERLAY 核心是 FACE_FLUSH。
13. INSERT 核心是 INSIDE_CLEARANCE。
14. resolved Joint 不得被 reload preset 覆蓋。

## Corner Invariants

15. STANDARD 永遠由最內實際 Fold line 定義。
16. ActualCorner = STANDARD + Semantic Delta。
17. 二級只能由最終實際 cutting topology 判斷。
18. 3D solver 不得改寫 STANDARD。
19. Corner policy 必須看 nearby Joint，不只看 assembly_type。

## Output Invariants

20. 2D / 3D / FinalScene / DXF / NC / Solver 共用 resolved geometry。
21. 同一 topology 的尺寸、Fold、Corner、hole 必須一致。
22. Save / Reload 後 Joint Graph、blank、Corner、topology fingerprint 不得漂移。
23. 新增任何 Intent / Joint relation 必須自動加入 regression matrix。

---

# 55. 一句話 Source of Truth

> **先把整體包外、板件成形包外與料尺寸分清楚；組合方式只是一組常用的逐邊 Joint preset；最終組裝真值是實體對實體的 AssemblyJoint Graph；每個 Corner 固定從真實 Fold Topology 取得 STANDARD，再依附近 Joint 的「面齊、進內緣、包覆、留肉、多切」語意做 delta；展開尺寸與 BEND 只讀同一份 material segment chain；2D、3D、DXF、NC、Solver、Save/Reload 全部只能消費同一份 Resolved Manufacturing Geometry。**

---

# 附錄 A：數值 fixture（只作已確認例子，不代表所有 Family 固定尺寸）

```text
T = 2
W = 400
D = 200

內邊框料 = 16
FW料 = 25
D 主面 formed outside = 198
D 主面料 = 194
下折料 = 15
左右側折料 = 15

Y blank = 16 + 25 + 194 + 15 = 250
INSERT X formed main = 396
INSERT X material main = 392
INSERT X blank = 15 + 392 + 15 = 422

Top STANDARD = 15 × 41
Bottom STANDARD = 15 × 15

STANDARD formed bands = 194 / 196 / 198
OVERLAY confirmed FW-band retain = 1T in this fixture

WRAP fixture:
15 / 15 / 15, X reserve 2, Y reserve 1
=> 28×14 + 15×1
```

---

# 附錄 B：Receiving 已確認操作員尺寸串

```text
-24 / 24 / 29 / 350 / 800 / 350 / 29 / 18
```

已確認：

> **全部都是包外尺寸。**

不得直接塞進 material `len`。

實際 material segments 必須依每一段當下 real topology 反推。

---

# 附錄 C：開發交付阻斷條件

出現任一項不得交付：

- `assembly_type` 與 Top CornerType 互相覆蓋；
- 同一 Joint 在 Family 間改義；
- OVERLAY 只藏 Fold UI、3D 還有 Fold；
- Receiving 自己擁有 WRAP relation；
- 2D / 3D Corner 尺寸不同；
- 3D solver 覆寫 STANDARD；
- blank 由 final polygon bbox 取得；
- 二件／三件只保存一個總 blank；
- Save/Load 後 edge override 消失；
- 新 Intent 沒進 regression matrix；
- 未確認歷史數值被寫成正式母規則；
- 求解後仍有非法穿透。

---

# 附錄 D：本整合版的正式修正標記

## 已升格為正式規格

- 組合方式 = 高階 preset，不是全部四邊永久鎖死。
- 真正組裝 Source of Truth = AssemblyJoint Graph。
- 主面 = FW 所在面。
- INSERT default：四邊嵌入。
- OVERLAY default：上／左／右貼外，下嵌入。
- INSERT_OVERLAY default：上貼外，左／右／下嵌入。
- 包覆貼外 default：上貼外，左／右嵌入，下 WRAP。
- WRAP = 全域 Joint relation。
- STANDARD = 最內實際折彎線母體。
- ActualCorner = STANDARD + Semantic Delta。
- 尺寸三層模型。
- blank / bend positions 共用 material chain。

## 已降級為歷史值／待確認

- INSERT 固定 `1T` default。
- INSERT_OVERLAY 固定 `0.5T / 2T` default。

## 保留為已確認 fixture

- 上方 STANDARD 15×41（指定 15/16/25 fixture）。
- 下方 STANDARD 15×15。
- WRAP 28×14 + 15×1（指定 15/15/15、預留 2/1 fixture）。
- Receiving 後面板 W-2.5T。
- Receiving 操作員尺寸串為包外尺寸。

---

**END OF INTEGRATED SPEC**
