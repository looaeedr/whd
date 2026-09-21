---
whd_doc_role: CURRENT
whd_contract: assembly-joint-placement-marking
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 板件接合定位打標（Joint Placement Marking）設計規格

## 1. 目的

WHD 的「打標線」是實際製造用 `MARKING`，不是 UI 輔助線。

用途是在承接／定位的母板表面，以雷射淺刻線標示另一片鈑件實際應落下、貼合、焊接或定位的位置，使現場組裝可直接依板上刻線定位。

本功能不新增另一套板件幾何。所有打標必須由既有 authoritative manufacturing / assembly geometry 衍生。

## 2. 已存在的製造能力

Current WHD 已有：

- `CUTTING`：切割；
- `BEND`：折彎；
- `MARKING`：打標／刻字／定位記號；
- `CHECK`：驗證／輔助，不是加工。

`DrawingScene` 已支援 `MARKING` 的 LINE / POLYLINE / CIRCLE，DXF serializer 會建立 `MARKING` layer 並以既有加工色 211 輸出。

因此本需求是擴充 **MARKING 幾何來源**，不是另造 DXF layer 或另造 exporter。

## 3. Canonical term

**接合定位打標（Joint Placement Marking）**

定義：

> 由兩個實體板件在 authoritative assembly placement 下的真實 mating/contact footprint，反投影到「承接／定位母板」的 authoritative flat pattern，並以 `MARKING` 寫入 FinalScene 的製造定位線。

它不是：

- CUTTING；
- BEND；
- CHECK；
- dimension / annotation；
- 單純 2D 畫面提示；
- 由 bbox / 中心點 / 名稱規則猜出的線。

## 4. 使用者已授權的產品決策

### 4.1 打標 owner

預設只在**承接／定位母板（locator / receiver part）**上產生打標。

被放置的 attached part 不重複打同一組線，除非未來有明確 rule 要求雙邊標示。

### 4.2 打標內容

預設畫出 attached part 真實接觸 footprint 的**兩側定位邊界**。

對典型狹長框料／折邊接合，這代表兩條沿接合方向延伸的平行 MARKING 線，使現場可直接看出零件實際佔用寬度。

預設不畫短端封口線，避免將定位 footprint 誤認為 CUTTING box。

若某種 joint 的真實 contact topology 不是可辨識的狹長 strip，則 fail closed；必須由該 joint 的 marking rule 明確定義另一種 footprint mode，禁止自行近似。

### 4.3 打標長度

沿**完整真實接合長度**打標。

不得只在頭尾打一小段，也不得自行用固定節距做虛線。若 CAM 未來要做間斷刻線，屬後加工策略，不改 canonical MARKING geometry。

### 4.4 哪些 joint 產生打標

**不是所有 assembly contact 自動打標。**

每一種結構接合必須有 explicit marking policy / rule，至少決定：

- 是否產生 MARKING；
- locator / receiver part；
- attached part；
- locator contact surface / region；
- footprint mode。

沒有 rule 時不產生，禁止用「有碰到就全部刻」的 heuristic。

## 5. 不擴充既有 AssemblyJoint relation enum

Current `AssemblyJoint` relation 是：

- INSERT
- OVERLAY
- INSERT_OVERLAY
- WRAP

這些 relation 主要描述既有 BoxBody / EndCap 類機械關係。

內門框焊接／定位打標不是新的 INSERT/OVERLAY/WRAP 關係，因此不得為了本功能硬塞或偽造 `AssemblyJointRelation`。

接合定位打標是**由 authoritative placement/contact 衍生的製造 projection**；其 policy 可引用既有 AssemblyJoint，也可引用 Divider / Inner Door 等其他 authoritative assembly contracts。

## 6. 幾何 Source of Truth

### 6.1 禁止公式猜位置

MARKING 不得由下列來源直接決定：

- part bbox；
- renderer bbox；
- world origin magic constant；
- 固定 50/80/170 等畫面／產品數值；
- part name hard-code 座標；
- 2D 預覽上看起來合理的位置；
- 測試 fixture expected。

### 6.2 正確流程

正式流程：

```text
authoritative physical parts
→ authoritative assembly placement
→ formed true-thickness contact / mating footprint
→ locator part world skin with flat UV
→ world contact footprint backprojection
→ locator authoritative flat UV
→ clip / validate against locator final material
→ MARKING primitives
→ FinalScene
→ 2D / DXF / optional 3D presentation
```

WHD current `assembly_geometry` 已提供：

- `folded_mesh_with_flat_uv_from_polygon()`
- `MappedSkinTriangle(flat, world, side)`
- `world_skin_with_flat_uv()`

Current collision layer已有 generic barycentric world→flat backprojection能力。新的 marking projection 應共用這種 piecewise-affine UV mapping 原理，而不是再寫另一套座標公式。

## 7. Contact / footprint 判定

### 7.1 合法 contact，不等於 penetration

接合定位打標要找的是**合法 mating/contact**，不是 collision relief 的非法 penetration。

不得把「collision crossing」直接當 marking footprint。

必須能區分：

- legal face/end contact；
- illegal penetration；
- incidental touch；
- unrelated nearby geometry。

只有 marking rule 指定的兩個 physical parts / regions 之合法 mating footprint 才可產生 MARKING。

### 7.2 真板厚

footprint 必須以 actual formed sheet / true-thickness contact 為依據。

不得只用 zero-thickness mid-surface 然後把板厚另用 magic T 偏移猜出兩條線。

## 8. Receiving Inner Door 首個正式案例

### 8.1 Current authoritative topology

Receiving 上方內門：

- top frame：獨立 physical part；
- left frame：獨立 physical part；
- right frame：獨立 physical part；
- **沒有獨立 bottom frame**；
- 下方水平 Divider 本身具有 `SHARED_LOWER_FRAME` role；
- bottom-frame placement 直接指向 exact Divider stable identity。

Frame spans 由 canonical Door geometry 推導：

- top span = inner door actual width；
- left/right span = inner door actual height；
- left/right frame 一路落到 shared horizontal Divider。

### 8.2 第一個 marking rule

對每一組有 shared lower Divider 的 Receiving inner door：

- locator / receiver = 該 exact horizontal Divider physical part；
- attached parts = 該 inner door 的 left frame、right frame；
- 在 Divider 實際承接面上求兩支豎框下端的 true contact footprints；
- 每個 footprint 反投影回 Divider flat pattern；
- 各輸出兩條 longitudinal `MARKING` boundary lines；
- MARKING 長度取該真實 contact footprint 的完整接合長度；
- 不得另外建立 fictitious bottom-frame part。

因此一個標準上方內門至少會在 shared Divider 上得到：

```text
左豎框下端定位 MARKING：2 條
右豎框下端定位 MARKING：2 條
```

實際座標由 contact/backprojection 決定，不在規格中寫死。

## 9. 其他 frame-to-frame 接合

Top ↔ Left/Right 等其他內門框接合，也應使用同一 marking projection 能力，但只有在：

1. authoritative placement 能解析；
2. 真實 mating/contact 能辨識；
3. family marking rule 指定 locator owner；

三者都成立時才產生。

若 owner/contact 語意尚未被 authoritative rule 定義，先不產生；禁止從畫面方向猜「哪一支是母板」。

## 10. FinalScene / DXF

接合定位打標必須進 canonical manufacturing FinalScene，layer 固定使用既有：

```text
MARKING
```

不得：

- 新增 `JOINT_MARK`、`SCRIBE` 等平行製造 layer；
- 把線放到 `CHECK`；
- 把線混進 `BEND`；
- 把線轉成 `CUTTING`。

DXF exporter 不應有 joint-specific 幾何邏輯；它只 serialize FinalScene。

## 11. 2D / 3D 顯示

- 2D manufacturing preview：必須顯示同一份 FinalScene MARKING。
- DXF：必須輸出完全相同的 MARKING primitives。
- 3D：若顯示刻線，只能把同一份 flat MARKING 隨板件 fold/placement 投影到 formed surface，屬 presentation；不得另算 marking 座標。

## 12. Persistence

接合定位打標是 derived manufacturing geometry。

Project Save 應保存的是：

- authoritative topology；
- part identities；
- placement / assembly state；
- marking policy 所依賴的真正產品 state。

不得把每條 MARKING 的座標另存成第二份 project truth。

Reload 後重新 canonical resolve，必須得到相同 stable part identities 與 MARKING geometry。

## 13. Dynamic topology

Door layout、inner-door enablement、Divider stable identity、frame topology 改變時：

- 舊 marking 必須消失；
- 新 marking 必須從 current authoritative physical parts 重新 resolve；
- 不得殘留 stale marking 對舊 stable ID。

## 14. Fail-closed

下列任一情況不得輸出猜測 MARKING：

- locator part 不存在；
- attached part 不存在；
- stable identity stale；
- contact footprint 無法唯一解析；
- world→flat backprojection 失敗；
- projection 超出 locator final material；
- footprint topology 不符合該 rule 的 mode；
- 只有 bbox/centerline evidence，沒有 physical contact evidence。

## 15. 最低驗收

### Geometry

- MARKING 來源是真實 contact footprint；
- world→flat round-trip 在 tolerance 內一致；
- line 完全落在 locator Final Material；
- 不修改 CUTTING / BEND / holes / relief；
- true-thickness contact 與 illegal penetration 分類不可混淆。

### Receiving Inner Door

- upper inner door 沒有 fictitious bottom frame；
- shared horizontal Divider exact stable identity 被保留；
- left/right frame 各在 Divider 上產生一組定位 MARKING；
- layout ratio / 尺寸改變時 mark 跟著 authoritative placement 移動；
- divider/frame stable identity 不變時不得因 redraw 產生不同 marking identity；
- boundary 消失時相關 marking 一起消失。

### DXF

Save → reopen 後：

- `MARKING` LINE 數量與 FinalScene 一致；
- coordinates 一致；
- layer = `MARKING`；
- CUTTING / BEND entity set 無 drift。

### Persistence

Save → Reload 後 canonical marking geometry 一致，且 project 不保存 derived marking coordinates。

## 16. 非目標

本階段不處理：

- CAM 雷射功率／速度；
- 打標深度；
- 機台 specific layer mapping；
- 虛線節距；
- 文字編號／QR code；
- 焊接符號；
- 人工拖曳 marking。

這些屬後續 CAM / presentation policy，不得污染第一階段 contact-derived geometry。
