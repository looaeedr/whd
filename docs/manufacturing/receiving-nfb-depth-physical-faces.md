---
whd_doc_role: CURRENT
whd_contract: receiving-nfb-depth-physical-face-and-second-side-fold
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

# 受電箱 NFB 深度：不折底板反推、左右雙折與底板固定片 Z／打標

來源：使用者 2026-10-18（Asia/Taipei）對話確認的實體面算法；#1502、#1503。
本文件是原有 [大片底板固定片焊接規則](receiving-large-weld-ear.md) 的**補充**，不取代 670×210／670×140 之 X／Y 孔位和 T3 固定片來源。

## 一、使用者指定的計算方式（CONFIRMED PRODUCT RULE）

**先把兩顆 NFB 各自當作「不折」的底板，求出真實正反面，最後才反推折邊。**
不要直接從展開圖的兩條 BEND 線距離、名義包外、或 3D 板件中心面猜 33。也不要預設「內門偏移 80」已經是實體面；範例的 80 是 *內門朝外實體面* 經核實時才可使用的座標。

- Z 相對基準：外門朝外**實體面 = 0**，朝箱內為正。內門朝外面 = 80，內門板厚 T2，故內門朝底板的實體面 = **82**。
- **NFB 深度是內門內側面 → 底板 NFB 安裝正面的淨距離**；兩者間沒有板厚扣除。
- 士林 400 型深度 **107**：底板正面 = 82+107 = **189**，底板背面 = 189+2 = **191**。固定片**貼合面 = 191**，兩者貼合間隙 **0**；大片固定片 T3 時背面 = **194**。
- 士林 125 型深度 **72**，先假設另一片不折：底板正面 = 82+72 = **154**，底板背面 = 154+2 = **156**。
- 兩個 NFB 正面高低差 = 189−154 = **35**；107 側**正面**到 72 側**背面** = 189−156 = **33**。
- 所以此組底板左右雙折：**第一段 −40 固定、第二段 33**。第二段應隨**所選品牌／型號的實際深度差與底板 T**變化，不得對所有品牌或型號寫死。
- 不使用 K-factor、折彎補償、虛構多扣一個板厚的算法。

| 實體面（全部是距外門實體面的 Z，mm） | 士林深 107 | 士林淺 72 |
| --- | ---: | ---: |
| 內門朝外面 | 80 | 80 |
| 內門朝箱內面 | 82 | 82 |
| 不折底板的 NFB 安裝正面 | 189 | 154 |
| 不折底板背面 | 191 | 156 |
| NFB 實際淨空 | 107 | 72 |

## 二、程式對上述計算的理解（DERIVED IMPLEMENTATION RULE）

令 `F` 為內門**朝外的實體面**相對外門實體面的距離，`Ti` 為內門厚度，`Tb` 為底板厚度，`Tf` 為固定片厚度，`Ddeep`／`Dshallow` 為 CSV 中**實際選定**型號深度（`Ddeep>Dshallow`）。

```text
inner_inside   = F + Ti
deep_front     = inner_inside + Ddeep
deep_back      = deep_front + Tb
ear_contact    = deep_back                   # 底板背面貼固定片正面，0 間隙
ear_back       = ear_contact + Tf
shallow_front  = inner_inside + Dshallow    # 先當不折底板
shallow_back   = shallow_front + Tb
mount_face_step= deep_front - shallow_front = Ddeep - Dshallow
second_return  = deep_front - shallow_back
               = Ddeep - Dshallow - Tb
first_return   = -40                        # 已確認固定
```

士林 `(107−72)−T2=33`；東元 `(103−68)−T2=33` 是*各自 CSV 值推導*，不是「凡同廠牌 400 型必為 33」的硬編碼。其他深度組合應改變結果；來源缺值或 `Ddeep−Dshallow<=Tb` 必須阻斷，不得猜測。

**35 mm 是兩個 NFB 安裝面之間的真實 Z 差；33 mm 是以「深型正面 ↔ 淺型背面」反推的第二折目標，不可當成通用的『兩道折線間料長＋兩 T』或直接說 33 的包外就是 35／37。** 加工展開、折向、兩面實際折後平行與否仍須由同一組已驗證折彎幾何及真實 3D 實體皮面量測。不得為了符合算式任意改動原圖 BEND 座標或製造 CUTTING。

## 二之一、原始 DXF 真實 BEND 站位（2026-10-18 來源覆核）

讀取使用者已提供的 `受電箱底板(5).dxf`（SHA-256 `cccf060cf6ff704b717dff0edd01d522c559cbf4ca98f5113ad84c9f4160d29b`），從 `BENDING` 層四條豎線取**實際**站位（不靠現行程式或前一輪錯誤測試反推）：

- 中間底板 CUTTING 原始 X 最小 `5268.49589`，X 最大 `6040.49589`，幅寬 **772 mm**。
- 左側兩道線原始 X `5308.49589, 5341.49589`，換算相對 X **40, 73**，間距 **33 mm**。
- 右側兩道線原始 X `5967.49589, 6000.49589`，換算相對 X **699, 732**，間距 **33 mm**。
- 製造展開的 `side_fold = 40 + 33 − T2 = 71` 是**裁切輪廓／拓樸料長佔用**，並不是第二道 BEND 線位置。把 `71` 當成第二道線會令第一／第二 BEND 只有 **31 mm**，不符用戶原圖。
- 因此 `sheetmetal_part_adapters.py` 的第二道左線須為 `first+second=73`；右線為 `blank_w-(first+second)=699`。第二段變動時同理。**不可把原圖標 33 改造成 31。**
- `CUTTING` 層中間底板實際輪廓有 **20 點**，局部座標肩部 X **74／698 mm**（而非舊程式的 71／701），端部有 **5 mm 截角**。外緣高低肩 Y=35、40、200、205 mm（當此樣本 H=240），中間頂底面從 X=79 到 693；同圖 `BENDING` 站位則是 40／73／699／732 mm。**裁切輪廓、BEND 站位、展開拓樸 71 mm 是三種不同數值，不得互相冒充。**
- 本次已依來源修正 CUTTING 20 點輪廓與 BENDING 站位，並加入由原始 DXF 獨立量測之測試。這只核證 **2D 源圖比對**，**折向與折後兩 NFB 實體面 Z 差 35，以及固定片焊接打標，仍須用實際 3D／DXF 逐項驗證**，不能僅憑此修正宣告全部製造就緒。

### 製造工作面及底板固定片孔的後續接線（相同 #1502）

- 原 `receiving_nfb_base_process_projection.py::build_existing_receiving_base_with_verified_nfb` 直接令 `side=71`，將 `X=71..701` 當整塊 NFB 安裝面，與新的真正 CUTTING x74..698 不符，真 DXF 製造回歸因此正確 RED。
- 修改為讀**實際 `PartRenderData.fold_guides`** 的四道側邊 BEND；內側兩條站位 x73/699 配合 T2 的半厚，取中心工作面 x74..698；再由既有 `_work_face` 驗證該面落在真正 CUTTING 物理輪廓內。不得關掉幾何防護或假改舊測試。
- 原 `ae._receiving_base_weld_ear_mount_slots` 寫死中間底板展開孔距 `732`；這只對原 W772 有效。當選定深度使第二折例如由 33 變成 28，W772→W762、每側展開返折佔用由71→66，原固定孔展開孔距732→722，而**折後仍維持 670**。不可為了保住原圖732而讓新版改深度後製造崩潰。
- NFB 螺絲孔與底板固定片的 4 個長圓孔仍各自擁有原加工 owner，不能把一種孔群當另一種；上述修正仍**不等於焊接 Z、真正 3D 或整箱製造驗收放行**。

## 三、固定片 Z 與 MARKING

底板連同左右兩片「底板固定片」**在 Z 一起移動**，固定片安裝面始終貼住不折底板背面；同一組 107/72 不是兩組獨立焊接高度。固定片焊在箱身左右側板**內側實體面**。

- **必須產生固定片貼合位置的 MARKING**（使用既有受電箱底板／側板加工標線規則），從 `ear_contact` = deep_back 的 Z 轉投影到**真實側板** 2D/展開面，按真實固定片外形／接觸幾何及左右各自定位標示。
- 範例的 Z 打標基準是 **191 mm**（假設 `F=80` 經實體面認證），但**191 不是 DXF 任意可畫線的 UV 座標**。不得將它直接當作 2D X／Y，不能用孔心或固定片名義邊緣替代真實接觸位置。
- 固定片 T3 的背面 194 是獨立面；不能把貼合面 191 誤算成 194，也不能重扣 T2。
- 同一批 NFB 變更深度，實際 `ear_contact`、底板位置、側板 MARKING 都隨之移動；內門自身 Z 固定（除非使用者更改既有內門縮入設定）。

## 四、現有程式問題與交付界限

1. `ae_engine/assembly_placement.py::_inner_door_geometry` 現時把 80 用來算**板件 placement center**；不能冒充內門朝外皮面。必須從 folded mesh 的實際內門外／內 skin 與 world transform 求出 `F`。
2. `_base_plate_center_plane` 現時由後側箱身內面和 `base_plate_bend` 決定，尚未採用 CSV NFB 深度；不得拿舊組合體中心 Z 當正確 NFB 安裝面的實測。
3. `sheetmetal_part_adapters.py` 的 `-40／33` 與 `40+33−T` 不能混成同一個站位；本次已按來源更正 BEND 為 40/73 與 699/732，但這**不會自行證明**實體 NFB 面差 35；未驗證真折向與皮面前不能解除 3D/DXF 製造護欄。
4. `ae_engine/receiving_nfb_depth_surface_policy.py` 負責純實體面算式、拒絕不合法深度，不能視作已完成裝配畫線／製造。
5. #1502/#1503 需驗證真 3D、側板雙邊 MARKING、固定孔投影、接觸／碰撞、Save→Reload、DXF export→reopen 與 CI，才可宣稱**交付完成**；純計算測試只證明本節尺寸鏈。

## 四之一、實體 3D 皮面定位的獨立計算

新增 `ae_engine/receiving_nfb_world_skin_datums.py`：先由現有 `build_inner_door_panel_render_data`、內門 19 mm 四邊折彎設定、真實 `fold_guides` 與共享 `world_skin_with_flat_uv` 取得**內門中間 NFB 工作面**的朝外及朝內兩張實體皮面，而不是使用 `resolve_inner_door_panel_placement` 的折後包絡中心 Z。再以箱身世界座標（+Z 朝外，往內是 −Z）計算：

```text
inner_inside_world_z = folded_inner_door_core_inside_skin
base_mount_front_z   = inner_inside_world_z - Ddeep
base_back_z          = base_mount_front_z - Tb
fixing_contact_z     = base_back_z      # 直接貼合，0 mm 空隙
fixing_back_z        = fixing_contact_z - Tf
shallow_front_z      = inner_inside_world_z - Dshallow
shallow_back_z       = shallow_front_z - Tb
```

**這是來源 FinalScene 皮面的深度要求／目標，不是已經移動 3D 底板的證明。** `assembly_placement.py::_base_plate_center_plane` 仍有由後側板推 Z 的歷史邏輯；還須將底板的真實折後**NFB 安裝皮面**與上述 `base_mount_front_z` 對齊，並帶動左右固定片及真實側板 MARKING。未完成這個幾何核對時，不能宣稱「3D 已修好」或解除 MFG-2 出圖阻擋。

## 四之二、#1502 實際組合體底板 Z：折後 35 不可硬當料長 33

本次串接路徑為 `receiving_base_plate_3d_profiles`（真正 CUTTING/BEND）→ `assembly_geometry_folded_mesh._profile_geometry`（只有 CENTER 第二折持有 `formed_length`，**展開 BEND 站位仍累計原料長**）→ `receiving_base_plate_real_skins`（從同一 FinalScene 與真正 T2 皮面求出 NFB 平行工作面；按來源尺寸快取）→ `receiving_nfb_world_skin_datums`（內門真實內側皮面）→ `assembly_placement.resolve_base_plate_placement`（設定世界 Z）。

- 士林 107／72：料長第二段 **33**，折後兩個 NFB 安裝皮面世界 Z 差 **35**；兩張皮面各離內門實體內側 **107／72**。不得用原先 `-D/2 + T + BEND/2` 當已提交型號的底板 Z；此式僅可留在**未配置預覽**。
- 型號或內門縮入改變，底板組合位置重新計算；來源尺寸相同時折後皮面網格按不變參數快取，不在每次渲染無意義重建。若第一／第二折真實皮面不共面或失去來源身份，拒絕以舊基準代替。
- **交付界限**：這一階段計算並實際連接**中間底板本體**的 Z。左右固定片仍是來源輪廓預覽，沒有真 3D 焊接與側板左右 MARKING，不能宣告 #1502/#1503 MFG-2 完工。此位置計算不修改使用者已提交的深度、也不釋出 DXF。

## 四之三、已提交 NFB 同一行的真正 Base Plate XYZ

前述 #1502 底板真 Z 雖正確，但舊底板根目錄組合位置 Y=0 並不等於內門已配置 NFB 列。現使用 `receiving_nfb_base_assembly_xy.receiving_source_nfb_base_assembly_xy`，對**同一目前 Set/Bay**、**同一內門上層**、**同一 NFB 安裝列**讀取既有 `project_nfb_inner_door_nominal_y`，並由 `assembly_placement.resolve_base_plate_placement` 把 **XY 與真實 skin Z 一次套到同一底板**。

- H1600，NFB 第一列距箱頂 550：world Y=250；操作高度改為 330：world Y=470。沿用 UI 設定來源，不再自己加減整箱高度。
- 只有全部 NFB 的 `manual_x_state=CONFIRMED`、X 為有限數值及對應來源 revision/snapshot 齊全時，才以真實 NFB X 範圍的中心設底板世界 X。X 未確認時保持預覽預設 X=0，絕不可標記已通過製造 X。
- 同一張底板若兩個 NFB 孔列的實際 world Y 不同，**必須 fail-closed**，不能借用第一列的位置讓第二列仍宣稱已符合。
- 相同列的兩顆 NFB 共用 Y 幾何求解／FinalScene，以免每次組合 3D 重複重算。
- **範圍仍有限**：這是已提交雙深度 CENTER 底板之 XYZ，未涵蓋無雙深度的 LEFT／RIGHT 單顆底板、以及左右底板固定片的真實焊接 skin/MARKING。後兩項保持 OPEN，不得完整 MFG-2 放行。

## 四之四、左右平側底板：單一來源型號的實體 Z

前面的「35 mm 面差」只屬於 **CENTER 雙折雙深度** 底板。`LEFT_FLAT_SIDE`、`RIGHT_FLAT_SIDE` **無側折**，但仍各有上／下 20 mm 折邊；不能因為沒有深淺兩顆深度差，就把平底板放回舊的箱體後側 Z。

- 本次只有**已提交的當前 Set/Bay**、單層同一列、唯一來源廠牌／型號深度時，透過 `committed_receiving_flat_nfb_depth_mm` 讀取 `開關索引.csv` 或 nfbv5 數值資料的深度（例如士林 400=107，另一個來源型號可能是 68），不設第二套底板「深度」輸入。
- 走**同一** `receiving_base_plate_real_skins` 取得平面底板的真 T2 NFB 安裝皮面；`resolve_receiving_nfb_world_skin_datums` 對齊內門朝箱內 skin；`assembly_placement` 套用相同來源的 XY 與 Z。換型號深度時，底板位置與固定片接觸的**目標 Z** 一起改，內門不動。
- **平底板兩顆不同型號**或**兩列**不能偷用最深一顆並聲稱全都貼合。若需要 PAD／其他實體底板，必須由其真實孔列及裝配來源驗證；缺項拒絕，不退回箱體後側 preview 冒充有來源的配置。
- 上述仍不代表大片固定片已擁有正式原圖 BEND。此固定片與側板兩側打標需獨立通過真實折向、物理接觸與回投影驗證後才准放行。

## 四之五、底板固定片世界座標目標與 NFB X 分離

大片底板固定片的 X 是**箱身左右側板焊接基準**，不是 NFB 開關孔列的 X。W800/T2 的兩片耳朵焊接側板內側真實 X=-398／+398，固定孔世界 X=-335／+335，裝配孔距670；所以整片底板必須維持世界 X=0。NFB 孔心即使人工確認在 -130／+70，**只能在底板加工投影內改 X**，不能把整片底板搬成 X=-30 造成耳朵與固定孔脫離。

`receiving_base_fixing_plate_z_targets.py` 以已存在的大片耳朵 source XY mating（`receiving_base_fixing_plate_mating.py`）與同一真實 `BasePlate` assembly Z、真實 T2 安裝面，產生兩片焊接固定片世界位置**需求／接觸目標**。CENTER 原始孔距 670×140：預設 NFB 所在列世界 Y250，兩片耳朵固定孔世界 Y180／320；NFB 高度改 330 則固定孔一起變 Y400／540。底板背面 Z 與固定片前接觸面 Z 必須相等（0 間隙），固定片來源 T3 往箱內方向延伸。

**但目標座標不是已認證加工結果。** 原始大片耳朵 DXF 並無正式可核准 BEND，故新目標的 `source_bend_verified`、`formed_weld_contact_verified`、`side_plate_marking_export_approved`、`manufacturing_ready` 均保留 `False`。真實側板 3D 皮面交集與展開 UV 回投影尚未解出以前，**不可據此自行輸出 MARKING 線或解開 MFG2**。

## 五、資料與向下相容

- 型號來源必須從 `基準檔/開孔/NFB/開關索引.csv` 或 V5 各品牌 `基準檔/開孔/NFB/數值規格/<品牌>/NFB數值規格.csv` **以被選中的 brand/model 查取深度**。不可從檔名尾碼或其他品牌推斷。
- 單層兩顆不同 NFB 的第二折尺寸，從**已提交之目前 Set/Bay** 的 NFBConfig 實際型號，配合該 Set `switch_brand` 的 CSV 深度求得。GUI `receiving_base_plate_values` 傳給**現有** `BasePlatePartSpec`／FinalScene，不額外建立第二種可編輯底板深度或品牌。
- Fold Designer 若尚未展開根層 NFB alias，只可使用**唯一 Set／唯一 Bay 的已提交資料**，或具身份匹配的指定當前 Set/Bay；多 Bay 未選或模型來源不符禁止跨箱套用。未提交／相同型號保持舊預覽，不能把 preview 33 當製造認證。
- UI 上未提交的深度配置不得回寫 Family 預設值；沒有明確配置時既有板件可維持預覽，但無憑證不得釋出 NFB 製造 DXF。
- 本確認覆蓋舊 #1503「底板／固定片位置永遠不動」文字；**內門固定、底板及固定片隨實際深度一起調 Z**。PAD 是另外的情形，不要拿尚未認證的墊高件替代雙折底板。

