# Phase6 尺寸語意與標準截角母規則

## [CURRENT] 名稱與 Family 補償硬性對照

- `OVERLAY = 貼外`。
- `INSERT_OVERLAY = 嵌入貼外`。
- `包覆貼外 = 高階 preset`。
- `WRAP = 下方局部包覆 Joint`；**包覆貼外 ≠ OVERLAY ≠ WRAP**。
- Receiving EndCap D core = `D - 2T`。
- Vault EndCap D core = `D - 3T`。
- `40×23 + 16×4` 只能標為 linked-FW INSERT_OVERLAY fixture；標準 OVERLAY current fixture 由 `ENDCAP_TOP_OVERLAY_STANDARD_V1@3` 推導為 `40×39 + 15×2`（T2/side15/FW25/ytop1=16）。
- formed FW 只可作 3D shadow/collision evidence，不得作正式 CUTTING oracle。

> **狀態：最高優先級機械語意規格（2026-08-30 使用者逐條確認）**
>
> 本文件專門固化 Phase6 最容易被 AI 混淆的三件事：
>
> 1. **包外尺寸 / 料尺寸 / 成形後板件尺寸**到底是哪一層；
> 2. **STANDARD 標準截角**如何由折彎線自然得到；
> 3. `INSERT / OVERLAY / INSERT_OVERLAY / WRAP / RETAIN / EXTRA_CUT` 如何只能從 STANDARD 衍生，禁止每一種類型自己發明一套截角公式。
>
> 若本文件與 2026-08-30 以前的 `CONTEXT.md`、`截角類型.md`、WHD 幾何規範、Certified Registry 舊公式說明或舊 regression 數值衝突，**以本文件的「尺寸語意與 STANDARD 母規則」為準**。舊數值可保留作歷史 fixture/evidence，但不得反過來推翻本文件已確認的物理語意。

---

# 0. 先讀：禁止再混用的詞彙

## 0.1 「包外尺寸」不是「外側包覆」

這兩個詞只有中文字接近，機械意義完全不同：

- **包外尺寸**：尺寸量法。表示折彎成形後，量外側面所得的尺寸。
- **外側包覆 `WRAP`**：裝配 / Joint 語意。表示某板件在指定位置包覆另一板件，並依該位置的目標面形成局部截角/留肉/多切。

**禁止**看到「包外」兩字就判斷 `WRAP=True`。

**禁止**因為 `WRAP` 開啟就把 15 料改成 18、19、20。折邊的料尺寸與其包外尺寸有自己的固定轉換；WRAP 是另外一層裝配語意。

---

## 0.2 「貼外 `OVERLAY`」不是「包外尺寸」

- `OVERLAY` 是組合語意。
- 「包外尺寸」是尺寸語意。
- `OVERLAY` 的核心物理意義是：**指定的成形面要和對方的目標面齊（面齊）**。

因此不能把 `OVERLAY` 粗暴翻譯成「沒有折彎，所以直接用 W」，也不能把所有 `+T / +2T` 都叫作 OVERLAY 補償。

---

## 0.3 「料尺寸」與「包外尺寸」一定分欄保存

同一段板金必須能同時知道：

- 操作員/成形語意的包外尺寸；
- 板材上實際直線段的料尺寸；
- 折彎方向；
- 左右兩端目前實際存在幾條相鄰折彎；
- 由哪一條規則把包外轉成料。

**禁止**把包外值直接塞進 Fold Profile 的 material `len`，再由另一層重複加 T。

---

## 0.4 對話中的尺寸省略規則（AI 必須遵守）

### UI / 操作員輸入欄位

使用者在 GUI / 操作員輸入層看到的 W/H/D/FW 等尺寸，依本專案約定是**包外尺寸**。

例如：

```text
W=400
H=500
D=200
```

表示完整箱體的包外目標尺寸。

### 討論折邊時未特別說「包外」

如果使用者在製造討論中只說：

```text
左右折 15
內邊框 16
FW 25
```

而**沒有特別說「包外」**，一律先按**料尺寸**理解。

例如 T=2：

```text
料 15 -> 若只有 1 個相鄰折彎 -> 包外 17
料 16 -> 若只有 1 個相鄰折彎 -> 包外 18
料 25 -> 若左右各有 1 個折彎 -> 包外 29
```

這條語言約定非常重要。AI 禁止把「使用者沒說包外的 15」自動當成包外 15。

---

# 1. 全系統尺寸分層

所有 Family、所有板件都使用同一套尺寸層級。不得把這套規則寫成「Receiving 專屬」。

## 1.1 第一層：整體輸入包外尺寸

典型：

```text
W / H / D
```

例如：

```text
W=400, H=500, D=200, T=2
```

代表組裝完成後整個箱體的包外目標。

---

## 1.2 第二層：各板件自己的成形包外尺寸

組合方式會先決定「某一片板件成形後本身應該多大」。

**這一步發生在料尺寸換算之前。**

例如 D=200、T=2：

- 箱身深度包外 = 200。
- 封頭 / 封尾為了裝入並保持各面正確，成形主面深度包外 = **198**。

已確認：這個 198 是**封頭 / 封尾自己的成形包外深度**，不是由 200 直接扣折彎數所得的料尺寸。

也就是：

```text
整體輸入 D=200
    -> 箱身成形包外 D=200
    -> EndCap 成形包外主面 D=198
    -> 再依 EndCap 自己的實際折彎 topology 換算料尺寸
```

**禁止**把「板件因裝配關係先變成 198」和「折彎換料再扣 T」混成同一步。

---

## 1.3 第三層：料尺寸

料尺寸是板材展平時，每一個直線材料段的實際長度。

全系統通則：

```text
料尺寸 = 包外尺寸 - (該材料段目前實際相鄰折彎數 × T)
```

相鄰折彎數由**當下真正存在的 Topology**決定：

- 0 個相鄰折彎 -> 扣 0T
- 1 個相鄰折彎 -> 扣 1T
- 2 個相鄰折彎 -> 扣 2T

若一條折彎被刪除，該折彎線消失的同時，左右相鄰材料段的「相鄰折彎數」也必須立即重新判定並重算料尺寸。

**禁止**刪掉 BEND 線但沿用原本 `-2T` 的 material length。

---

## 1.4 正負號只表示折彎方向

例如操作員語意：

```text
-24
```

其中：

- 尺寸大小 = 24
- `-` 只表示折彎方向 / orientation
- 負號不參與料長加減
- material segment length 必須是正長度

---

# 2. 展開尺寸與折彎線位置

## 2.1 展開總尺寸不另發明公式

每一段先由包外尺寸轉成正確料尺寸後：

```text
展開總長 = 所有料尺寸段直接相加
```

折彎線位置也是同一份料尺寸的 cumulative sum。

例如料尺寸：

```text
22 / 346 / 16
```

則：

```text
第一條 BEND = 22
第二條 BEND = 22 + 346 = 368
材料最外緣 = 22 + 346 + 16 = 384
```

**展開總尺寸與折彎線位置必須使用同一份料尺寸段。**

禁止：

- UI 算一套展開總長；
- 2D BEND 再算另一套 cumulative sum；
- 3D 再自己反推一次。

---

## 2.2 截角 / 開孔不改展開 W×H

例如原始展開料是：

```text
400 × 500
```

角落切掉 15×15，展開尺寸仍是：

```text
400 × 500
```

截角、止裂、孔洞、局部挖料：

- 會改 material polygon shape；
- 會改面積；
- **不會改原本由料尺寸段累加得到的 blank W×H。**

因此禁止用「截角後 final material polygon 的 bbox 變小」反推 blank W×H。

只有以下情況才重算 blank：

- 包外段尺寸改變；
- 折彎 Topology 改變；
- 實體板件拆分方式改變。

---

## 2.3 二件式 / 三件式必須逐片算

多片結構不得先算整體箱身展開，再從整體結果切分。

每一片實體板件都必須：

```text
自己的包外段
-> 自己當下存在的 Fold Topology
-> 自己的料尺寸段
-> 自己的 BEND cumulative sum
-> 自己的展開 W×H
```

至少要分別保存：

### 二件式

- 左箱身 blank
- 右箱身 blank

### 三件式 W 分割

- 左片 blank
- 中片 blank
- 右片 blank

### 三件式側背分離

- 左側板 blank
- 後面板 blank
- 右側板 blank

### 其他

- Head blank
- Tail blank
- Door / Base / Indicator 等每片各自 blank

禁止只有一個「箱身總展開料」去猜多片尺寸。

---

# 3. 後面板（Receiving 側背分離）

## 3.1 後面板是完全平板

使用者已確認：

> **後面板完全沒有折彎。**

所以：

- 不進 BA / BD / K-factor；
- 不套「每相鄰折彎扣 T」；
- 成形平板尺寸就是裁料尺寸。

---

## 3.2 後面板寬度

已確認公式：

```text
BackPanelWidth = W - T - T - 0.5T
               = W - 2.5T
```

例如：

```text
W=800, T=2
BackPanelWidth = 800 - 5 = 795
```

舊程式 / 舊文件的：

```text
W - 0.5T = 799
```

**已被本規則判定為錯誤舊規則，不得再作正式 Source of Truth。**

---

## 3.3 後面板高度

後面板高度依 Head / Tail 組合後對外部高度的占用決定：

```text
BackPanelHeight
= H
- HeadOutsideOccupancy
- TailOutsideOccupancy
```

目前已確認的端部外占語意：

- INSERT：0T
- OVERLAY：1T
- INSERT_OVERLAY：1T

例如 H=1600、T=2：

- INSERT + INSERT -> 1600
- OVERLAY + INSERT -> 1598
- INSERT + OVERLAY -> 1598
- OVERLAY + OVERLAY -> 1596
- INSERT_OVERLAY + INSERT -> 1598
- INSERT_OVERLAY + INSERT_OVERLAY -> 1596

因後面板完全平板，所以這個寬 × 高即為該片平板裁料尺寸。

---

# 4. EndCap / Tail Y 方向完整尺寸鏈

以下用使用者確認的例子：

```text
整體輸入 D=200
T=2
```

## 4.1 四段物理語意

Y 向由外到內/另一側依現有程式名稱對應：

| 程式名稱 | 實際物理意義 |
|---|---|
| `ytop1` | 內邊框，放門 |
| `FW` | 邊框 |
| `D` 主面 | 箱子的深度主面 |
| `ybottom1` | 與箱身接觸、焊接的折邊 |

---

## 4.2 已確認的包外與料尺寸

T=2 時：

### 內邊框 `ytop1`

```text
料 = 16
包外 = 18
```

### FW 邊框

```text
料 = 25
包外 = 29
```

### EndCap 深度主面

整體輸入 D=200，但 EndCap 自己的成形主面包外深度：

```text
198
```

該主面上下兩端都有實際折彎，因此：

```text
料 = 198 - 2T
    = 194
```

### 下方焊接折邊 `ybottom1`

```text
料 = 15
包外 = 17
```

---

## 4.3 Y 向總展開料

```text
16 + 25 + 194 + 15 = 250
```

所以：

```text
Y blank = 250
```

BEND cumulative position 亦由同一鏈得到。

---

# 5. EndCap / Tail X 方向：INSERT 基準

以下以：

```text
W=400
T=2
```

## 5.1 左右焊接折邊

左右 X 折邊物理語意與 Y 下方焊接折邊相同。

未特別說包外時：

```text
左右折 15 = 料尺寸 15
```

T=2、單一相鄰折彎時：

```text
包外 = 17
```

---

## 5.2 INSERT 下 X 主面成形包外

箱身整體包外 W=400。

封頭 / 封尾要嵌入箱身內：

```text
EndCap X 主面成形包外 = W - 2T
                       = 396
```

注意：396 是**板件成形包外**，不是料尺寸。

主面左右兩端都有折彎：

```text
X 主面料 = 396 - 2T
         = 392
```

所以一般 INSERT、有左右折彎時：

```text
15 + 392 + 15 = 422
```

因此：

```text
X blank = 422
```

---

# 6. OVERLAY X 向：必須保留兩層不同的 +2T 語意

這是 AI 最容易再次混掉的地方。

已確認的正確鏈：

```text
X 主面料 = 392
```

原本左右有折彎，因此先補回**原本折彎造成的包外補償**：

```text
392 + 左1T + 右1T = 396
```

這個 396 是原本的**成形包外基準**，即使左右 X BEND 在 OVERLAY 下消失，這個成形基準不能被抹掉或重新定義。

之後才套 `OVERLAY` 的「面齊」裝配語意：

```text
396 + 貼外語意 2T = 400
```

所以完整鏈是：

```text
392 料
 -> +2T（原本左右折彎的包外補償）
 -> 396 成形包外基準
 -> +2T（OVERLAY 面齊語意）
 -> 400 與箱身外框面齊
```

**這兩個 +2T 絕對不是同一件事。**

禁止簡化成：

```text
沒有折彎，所以 X=W
```

即使最後數字碰巧等於 W，這種簡寫會失去製造語意，之後必然造成回歸。

---

# 7. STANDARD：所有截角的唯一母體

## 7.1 STANDARD 永遠不變

使用者已確認：

> STANDARD 之所以叫 STANDARD，就是它「死死的」固定在那裡。
>
> 它不代表每一種工法都一定最好看、最好裝、最有間隙；它是永遠不變、永遠可以回復與比較的幾何母體。

因此：

```text
ActualCorner
= STANDARD
+ Semantic Delta
```

而不是：

```text
INSERT 有一套獨立公式
OVERLAY 再有一套獨立公式
INSERT_OVERLAY 再有一套獨立公式
WRAP 再有一套獨立公式
```

任何 CornerType / Assembly Intent 的調整值都必須能說清楚：

- 從 STANDARD 哪一個區段出發；
- 為什麼要少切（留肉）；
- 為什麼要多切；
- 目標是面齊還是進內緣；
- delta 是多少；
- delta 是否可調。

---

## 7.2 STANDARD 的幾何定義

**標準截法 = 從材料外緣截到該方向「最內部的折彎線」。**

不是第一條折彎線。

不是某個 CornerType 自己定義的固定尺寸。

不是 3D solver 任意給的一個 bbox。

---

# 8. EndCap / Tail STANDARD 範例

沿用 T=2、Y 料鏈：

```text
內邊框 = 16
FW = 25
D主面 = 194
下折 = 15
Y總料 = 250
```

X 左右折料：

```text
15
```

## 8.1 上方 STANDARD

Y 向最內部折彎線距外緣：

```text
16 + 25 = 41
```

X 向側折：

```text
15
```

所以：

```text
上方 STANDARD = 15 × 41
```

---

## 8.2 下方 STANDARD

X 側折：15。

Y 下折：15。

所以：

```text
下方 STANDARD = 15 × 15
```

---

# 9. STANDARD 截角後不同 X 區段的成形包外狀態

這一節是理解 INSERT / OVERLAY / 二級截角的關鍵。

Y 總料：

```text
250
```

上方 STANDARD：41。

下方 STANDARD：15。

若只看最外側 X=0~15 的截角帶：

```text
250 - 41 - 15 = 194
```

但是**不能把整個上方截角區都簡化成 194**。

因為 X 向還存在 FW 的 25 料寬區段。

完整分區：

## 9.1 X = 0 ~ 15

上、下對應折彎都在截角區被切掉：

```text
成形包外狀態 = 194
```

---

## 9.2 X = 15 ~ 40

`40 = 15 + FW料25`

這個 FW 區段：

- 上方折彎在 STANDARD 截角區被切掉；
- 下方折彎仍存在。

因此：

```text
194 + 1T = 196
```

所以 STANDARD 在 FW 區段形成：

```text
196 包外
```

---

## 9.3 X > 40

上下折彎都存在：

```text
194 + 2T = 198
```

即正常 EndCap 主面成形包外：

```text
198
```

因此同一片板，從外往內自然形成：

```text
194 -> 196 -> 198
```

這不是三套公式，而是 STANDARD + 實際還存在的折彎所自然形成的三個區段狀態。

---

# 10. OVERLAY（貼外）上方截角語意

## 10.1 貼外的母語意 = 面齊

`OVERLAY` 的核心不是「少一條折彎」或「固定 +T」。

核心是：

> **指定的成形面要和對方的目標面齊。**

---

## 10.2 在 FW 25 區段如何從 STANDARD 衍生

STANDARD 在 X=15~40 的 FW 區段是：

```text
196
```

正常主面 / 目標面是：

```text
198
```

所以貼外要讓該區段面齊 198：

```text
198 - 196 = 1T
```

因此：

```text
OVERLAY = 在 FW 區段相對 STANDARD 留肉 1T
```

T=2 時：

```text
196 + 2 = 198
```

---

## 10.3 下方此時不跟著留肉

使用者已確認：

> 下方不是跟該目標面齊，所以**不能因為上方 OVERLAY 留肉，就把下方也一起留肉**。

因此在這個上方 OVERLAY 語意中：

```text
下方 STANDARD 15×15 保持不變
```

**禁止**把「貼外 = 上下各留 1T」當成通則。

留肉必須看**哪個局部面需要面齊**。

---

# 11. INSERT（嵌入）上方截角語意

## 11.1 嵌入的母語意 = 進到對方內緣

以 D=200、T=2：

箱身內緣：

```text
196
```

STANDARD 在 FW 區段也自然是：

```text
196
```

但嵌入不能只是「剛好等於內緣」；工法上需要進得去，所以：

> **INSERT 在 FW 區段相對 STANDARD 做多切，使該區段成形包外 < 196。**

---

## 11.2 INSERT 仍是一級截角

非常重要：

**INSERT 有多切，不代表它變成二級截角。**

若幾何仍只有一個連續的一級切除輪廓，就仍是單級 / 一級截角。

禁止把「FW 區段需要多切」錯叫成「INSERT 二級截角」。

---

## 11.3 INSERT 預設多切量目前不得猜

已確認的是：

- 作用區：STANDARD 的 FW 區段；
- 方向：多切；
- 目的：讓 196 變成 `<196`；
- 數值可以依工法調整。

**本次對話沒有重新確認 INSERT 的正式預設多切量。**

因此 AI / 程式修改前不得自行把 `0.5T`、`1T` 或其他歷史值宣告為新標準；必須回查已認證資料或向使用者確認。

---

# 12. 二級截角的正確定義

## 12.1 二級截角不是「某個參數存在」

二級截角只有在**實際 CUTTING 幾何出現第二個階梯 / 第二個獨立切除區**時才叫二級。

以下都**不能**單獨證明它是二級：

- 有 `secondary_retain_t` 欄位；
- 有 0.5T；
- 有 FW；
- 有多切；
- 有 INSERT。

---

## 12.2 STANDARD 自然分區是理解基礎，但不等於自動二級

STANDARD 會因多條折彎線形成：

```text
194 / 196 / 198
```

不同 X 區段。

這些區段是**成形狀態分區**。

只有當最終 CUTTING 真正形成第二個 step / L shape / secondary band，才是幾何上的二級截角。

---

## 12.3 `0.5T` 不能被偷換成「二級截角定義」

歷史資料中有 `secondary_retain_t=0.5T` 等參數。

它只能代表某一已認證工法在 secondary 區域的**可調 delta / 留肉量**。

禁止寫成：

```text
二級截角 = 0.5T
```

更禁止把 0.5T 套到 INSERT 一級截角。

---

# 13. INSERT_OVERLAY（嵌入貼外）

## 13.1 不得從名稱猜「左 INSERT、右 OVERLAY」

使用者已確認：

- 同一片板可能同時存在嵌入與貼外語意；
- 左右通常相同，但可以不同；
- 標準情況 X 左右預設仍是嵌入；
- `INSERT_OVERLAY` 的關鍵不是把整片簡化成「左一種、右一種」。

---

## 13.2 真正差異發生在 STANDARD 的局部區段 / FW 折彎線周邊

已確認：

> 嵌入貼外的「貼外」語意與 FW 折彎線附近的留肉有關；不能把 STANDARD 全部切到底。

因此 `INSERT_OVERLAY` 必須表示為：

```text
STANDARD
+ 局部 INSERT（進內緣 -> 多切）
+ 局部 OVERLAY（面齊 -> 留肉）
```

而不是一條完全獨立的 dead formula。

---

## 13.3 本次尚未重新確認的內容

本次語意釐清**尚未把 INSERT_OVERLAY 的每一個 secondary 預設 delta 重新逐值確認**。

因此下列歷史值不得因為存在舊程式就自動升格為本文件的新確認值：

- `secondary_retain_t=0.5T`
- `secondary_depth_t=2T`
- 任何固定 primary/secondary dead dimensions

在真正修改 production registry 前，必須用本文件的 STANDARD 分區語意重新對照並取得使用者確認或明確的既有認證證據。

---

# 14. Receiving 下方 WRAP（「包覆貼外」preset 的下方局部包覆 Joint）

## 14.1 WRAP 是局部下方 Joint 語意

- 不屬於上方 `INSERT / OVERLAY / INSERT_OVERLAY` 高階組合方式。
- 發生在受電箱封頭 / 封尾的**下方**。
- 目標是和**側板的指定成形面齊 / 包覆該接合區**。

其高階物理原則仍與 OVERLAY 的「面齊」一致，但：

- 位置不同；
- target 不同；
- STANDARD 不同；
- CUTTING topology 可形成 L 型 / 二級。

禁止把 `WRAP` 與「包外尺寸」混在一起。

---

## 14.2 下方 STANDARD 不變

下方母體：

```text
15 × 15
```

WRAP 只能在這個 STANDARD 上衍生。

不能把 WRAP 的 28×14 說成新的 STANDARD。

---

## 14.3 目前已確認的 WRAP L 型例子

當：

```text
側折料 = 15
側板後折料 = 15
下折料 = 15
X 預留 = 2
Y 預留 = 1
```

則既有 L 型衍生幾何：

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

正確語意是：

```text
STANDARD 15×15
 -> 因下方 WRAP 要與側板面齊 / 包覆接合
 -> 在側板後折方向延伸避讓
 -> 同時保留指定預留肉
 -> 形成 L 型 / 二級衍生角
```

**28×14 + 15×1 是 STANDARD 的衍生結果，不是 STANDARD 本體。**

---

# 15. 「面齊」與「進內緣」是兩個最重要的 Assembly 語意

## 15.1 面齊

代表：

```text
此局部成形面最終要與 target face 齊平
```

若 STANDARD 下該區域比 target face 短：

```text
留肉 = target - standard_formed_result
```

典型：OVERLAY、局部 WRAP。

---

## 15.2 進內緣

代表：

```text
此局部成形區要進入 target 的 inside boundary
```

若 STANDARD 剛好卡在內緣或仍太大：

```text
相對 STANDARD 多切
```

典型：INSERT。

---

## 15.3 Registry 應保存「語意 + delta」，不是只存答案

已認證規則至少應能回答：

- STANDARD 是哪一個基準角；
- 哪個 segment/band 被調整；
- 目標語意：`FACE_FLUSH` / `INSIDE_CLEARANCE` / `RETAIN` / `EXTRA_CUT` / `WRAP`；
- target face / inside boundary 是誰；
- delta 如何由 T / 可調參數得到；
- 最終 topology level；
- 使用者可調值；
- rule revision / evidence。

禁止只存：

```text
40×23
29×39
28×14
```

這些只能是某組 fixture 的結果證據。

---

# 16. 展開尺寸資料化規則

使用者已明確要求：**展開尺寸必須進資料庫 / `.p6fold`，不能每個畫面當下亂重算。**

每一片 physical sheet 必須保存等價資料。以下欄位名稱是**建議 schema 名稱**，實作可依現有 `.p6fold` schema 命名，但語意與資訊不可省略：

```text
unfolded_blank:
  width
  height
  source_revision
  segment_chain_x
  segment_chain_y
  bend_positions_x
  bend_positions_y
  formed_dimensions_reference
  topology_fingerprint
```

其中每一個 segment 建議至少保存：

```text
name
physical_role
outside_dimension
material_dimension
bend_count_left_or_before
bend_count_right_or_after
bend_direction
source
```

對完全平板（例如 Receiving 後面板）：

```text
bend_count = 0
formed size = material size = blank size
```

---

## 16.1 UI / 2D / 3D / Assembly 不得各算一次

正確：

```text
canonical dimension model
 -> physical piece material segment chain
 -> blank record
 -> 2D / single 3D / assembly 3D / save-reload 共讀
```

禁止：

```text
2D formatter 自己加
3D renderer 自己量 bbox
assembly 又重算一次
save/reload 只存顯示字串
```

---

# 17. 使用者已確認的 Receiving 操作員尺寸串

下列串：

```text
-24 / 24 / 29 / 350 / 800 / 350 / 29 / 18
```

使用者已確認：

> **全部都是包外尺寸。**

不能直接當 material `len`。

以 T=2、依相鄰折彎數反推 material segments 時，必須由實際 topology 計算；不能因為此串出現在 Receiving defaults 就直接把 29、18 塞成料長。

歷史錯誤例：

```text
把包外 29 存成料 29
 -> renderer / profile 又補 2T
 -> 顯示成包外 33
```

這種資料層混用必須視為阻斷性 Bug。

---

# 18. AI 最容易重犯的錯誤（禁止事項）

## 18.1 把包外尺寸當外側包覆

錯：

```text
「包外 18」=> WRAP 開啟
```

正：

```text
包外 18 = 尺寸量法
WRAP = Joint / assembly relation
```

---

## 18.2 把 16 / 18 當成兩種工法尺寸

錯：

```text
一般=16、包覆=18
```

正：

```text
16 = 料尺寸
18 = T=2 時同一折的包外尺寸
```

與 WRAP 無關。

---

## 18.3 把 FW=25 / 29 當成兩套 FW

錯：

```text
Vault FW=25
Receiving FW=29
```

若語意未標明，這種寫法會混層。

正確要寫清：

```text
FW料=25
在兩側折彎、T=2時包外=29
```

若 UI 顯示 29，內部 material len 不能再存 29 後重複補 T。

---

## 18.4 把 W/H/D 直接當每片板件料尺寸

錯：

```text
D=200 => EndCap material D=200
```

正：

```text
整體輸入 D=200
-> 箱身包外=200
-> EndCap 自己成形包外=198
-> EndCap 主面 material=194（兩側折彎存在時）
```

---

## 18.5 把 STANDARD 截到第一條折彎線

錯：

```text
上角 15×16
```

正：

```text
STANDARD 截到最內部折彎線
上方 = 15 × (16+25) = 15×41
下方 = 15×15
```

---

## 18.6 把 41 重新命名成 FW

錯：

```text
FW=41
```

正：

```text
16 是內邊框料
25 是 FW 料
41 只是兩段 cumulative span / STANDARD Y depth
```

物理 role 不得因相加而消失。

---

## 18.7 把 OVERLAY 簡化成「沒有 X BEND，所以 blank W = W」

數值可能碰巧對，但語意錯。

正確鏈必須保留：

```text
392 material
-> +2T 原折彎包外補償
-> 396 formed baseline
-> +2T OVERLAY 面齊語意
-> 400 final flush result
```

---

## 18.8 把所有消失的折彎都補成留肉

錯。

只有**該局部面需要面齊**時，才依目標面做留肉。

例如已確認上方 OVERLAY：

- FW 區段留肉回 198；
- 下方不是同面目標，因此下方 STANDARD 15×15 不跟著留肉。

---

## 18.9 把 INSERT 的多切叫二級截角

錯。

INSERT 可以在 STANDARD 的 FW 區段做多切，但若最終幾何仍是一個連續切除輪廓，就是一級截角。

二級必須真的有第二個 step / band / L shape。

---

## 18.10 把 0.5T 當「二級截角本體」

錯。

0.5T 只能是某個已認證 secondary semantic 的 delta / retain parameter。

---

## 18.11 看到 3D 算出的數字就覆蓋 STANDARD

錯。

STANDARD 是死的母體。

3D 可：

- 驗證；
- 找未知 assembly relation 的 provisional evidence；
- 驗證面齊 / 內緣 / 零非法穿透。

3D 不可：

- 把 STANDARD 15×41 改成另一個 dead size；
- 看到 collision bbox 就重新定義 CornerType；
- 覆蓋已確認的尺寸語意。

---

# 19. 實作前強制檢查順序

任何人 / AI 要修改尺寸、Fold、Corner、Registry、3D 前，必須依序回答：

1. 這個使用者數字是**整體輸入包外、板件成形包外、還是料尺寸**？
2. 如果使用者沒說「包外」，依對話語言約定是否應視為料尺寸？
3. 這個 material segment 左右目前各有沒有實際折彎？
4. 包外 -> 料應扣幾個 T？
5. 該方向全部料尺寸累加是多少？
6. BEND cumulative positions 是否就是同一份 segment 累加？
7. STANDARD 的最內部折彎線在哪裡？
8. 此處 STANDARD 截掉後，不同 band 還剩幾條折彎、形成多少包外？
9. Assembly Intent 的目標是：
   - 面齊？
   - 進內緣？
   - 單純留肉？
   - 單純多切？
   - 下方 WRAP？
10. Semantic delta 是作用在哪一個 band？
11. 最終 CUTTING 是否真的形成第二級？沒有就不能叫二級。
12. blank W×H 是否仍由 segment chain 得到，而不是截角後 bbox？
13. 多片結構是否逐片計算？
14. Save / Reload 是否保存每片 blank 與 topology fingerprint？

如果以上任何一題答不出來：

> **停止修改，先向使用者確認。禁止猜。**

---

# 20. 目前仍需使用者確認、不得擅自補齊的項目

本文件只寫入本次已確認內容。以下仍不得自行猜：

1. INSERT 在 FW 區段的正式預設多切量究竟是多少；
2. INSERT_OVERLAY 每一個 secondary step 的正式預設 delta / depth 是否沿用歷史 0.5T / 2T；
3. 任何新的 Family 若有不同 target face / inside boundary，必須先確認其實際裝配面；
4. 未來若導入新的折彎物理模型，不得在未確認前改寫本文件的「包外 / 料 / STANDARD / 面齊 / 內緣」語意。

---

# 21. 一句話 Source of Truth

> **先分清楚整體包外、板件成形包外與料尺寸；料尺寸只由實際 Fold Topology 轉換；STANDARD 永遠截到最內部折彎線且永不改；INSERT / OVERLAY / INSERT_OVERLAY / WRAP 全部只能在 STANDARD 的局部 band 上用「進內緣 / 面齊 / 留肉 / 多切」語意做 delta；展開尺寸與 BEND 線只讀同一份料尺寸鏈。**
