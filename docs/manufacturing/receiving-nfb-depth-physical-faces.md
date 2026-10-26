---
whd_doc_role: CURRENT
whd_contract: receiving-nfb-depth-physical-face-and-second-side-fold
whd_canonical: null
whd_schema: WHD_DOC_META_V1
---

> **2026-10-26 最高優先：固定片接觸 Z 按當前廠牌整份 NFB V5 CSV 的已知最大深度定位，且同廠牌／內門實體基準下，不因選用型號或 NFB 層數變動。** 此規則覆蓋下文任何「固定片跟著各層 NFB 深度移 Z」的舊文字；底板若未補償至固定片零間隙，只能預覽，不得製造放行。詳見 [固定片廠牌最大深度 Z 規則](receiving-fixed-ear-brand-max-z-20261026.md)。

# 受電箱 NFB 深度：不折底板反推、左右雙折與底板固定片 Z／打標

來源：使用者 2026-10-18（Asia/Taipei）對話確認的實體面算法；#1502、#1503。
本文件是原有 [大片底板固定片焊接規則](receiving-large-weld-ear.md) 的**補充**，不取代 670×210／670×140 的 X／Y 孔位；現行固定片來源 T2／84／BEND23，固定片 Z 採 2026-10-26 廠牌最大深度規則。

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
- **已取代（2026-10-26）**：同廠牌選用 NFB 深度變更，**固定片接觸 Z／由其回投影的側板 MARKING 深度不動**；現有底板可能需額外深差補償與零間隙驗證，內門自身 Z 固定（除非實際內門縮入設定改變）。

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

## 四之三、每個 NFB 層的開孔群中心對底板中心（2026-10-18 使用者再次確認）

**最終定位修正（使用者 2026-10-18 確認）**：每一 NFB 層的**開孔高度 Y**決定對應底板的**組合中心 Y**；底板的**左右 X 永遠固定在箱體中心 X=0**，不跟隨 NFB 的 X 位移。NFB 左右修正只移動底板上的**該顆 NFB 螺絲孔 X**；底板固定孔 X=±335（折後孔距 670）及焊於側板的左右固定片不動。NFB 開孔從箱頂量得的高度（如 330／830）既是孔的定位，也決定對應底板的組合 Y；**不是底板成品高度尺寸**。先前 #1892 將這點反過來，硬把已配置底板 X/Y 留在 (0,0)，**不符合此次明確指定**。

- **外門上層的 NFB 每層一片底板及一組左右固定片**。同層多顆的開孔高度 Y 確定這層底板中心 Y；各顆 NFB 的 X 只投影至該片底板自己的 NFB 螺絲孔位置，不改底板及固定片的 X。不同 NFB 層分開計算與建實體。**外門下層分區**沒有本項 NFB 底板，並不代表 NFB 第二層沒有板。
- Y：既有 `project_nfb_inner_door_nominal_y` 會按世界座標投影每層開孔中心；對 H1600，從箱頂 330／830 時世界 Y 分別為 **470／−30 mm**。該層底板的中心 Y 必須等於此處開孔群中心，而**底板 H 仍由 `receiving_base_plate_values` 的板件規格決定**。
- X：**每片底板組合中心 X=0**；固定孔列折後 X=−335／+335，左右固定片依箱身左右側板內皮面各自裝配。NFB 孔群中心 X（即使已確認）**僅是螺絲孔加工的來源座標**，其位移不得傳遞到整片底板、底板固定孔、耳片或箱身側板。NFB X 未認證時不得放行螺絲孔 CUTTING；不可把 X=0 的底板組合基準說成未知時的預覽補值。
- Z：由內門朝內物理 skin、NFB CSV 深度和底板真正折後安裝 skin 對齊；士林 107／72 的實體安裝面差 35、展開第二折 33 的規則**不變**。
- 裝配順序：**底板 X 永遠以箱體置中、按 NFB 層孔群高度定 Y、由內門及折後物理 skin 算 Z → 左右固定片依此底板的固定孔（X=±335）裝配並焊在側板內面 → 來源確認的每顆 NFB X 僅投影該顆螺絲孔到不動的底板 → 接觸幾何通過後才允許側板 MARKING**。修改單顆 NFB X 絕不移動底板／固定片。
- 現有根 `base_plate` 只有一個實體身份：**僅在來源確定只有一個 NFB 層時**，可使用 `receiving_nfb_layer_centers` 的**層 Y**放置，但 X 固定 0。新每層資料以 `base_plate:nfb_layer:<layer_index>` 作獨立定位標識；如有兩層，必須由下游建立兩份板件／固定片且經 3D/製造驗證，**不能把一個 root plate 冒充已產生兩片**，也不能把兩層孔心平均成一片。
- **層索引和顆索引是兩回事**：`layer_index` 是內門上層作業區中的 NFB 第幾層，`slot_index` 是該層左右第幾顆。只選一個 NFB 層時，左右兩顆的 `slot_index=0/1` 都屬同一片底板；配置兩層時必須有明確 `layer_index`，不可拿第二顆 `slot_index=1` 假扮第二層。
- 先前 #1892 的「固定片先決定底板 XY，孔位不得影響底板位置」屬**錯誤解讀，已撤回**；左右側板上的固定片實體折向及 MARKING 仍要通過獨立幾何回投影驗收，未完成前不可當成已出製造圖。

## 四之四、左右平側底板：單一來源型號的實體 Z

前面的「35 mm 面差」只屬於 **CENTER 雙折雙深度** 底板。`LEFT_FLAT_SIDE`、`RIGHT_FLAT_SIDE` **無側折**，但仍各有上／下 20 mm 折邊；不能因為沒有深淺兩顆深度差，就把平底板放回舊的箱體後側 Z。

- 本次只有**已提交的當前 Set/Bay**、單層同一列、唯一來源廠牌／型號深度時，透過 `committed_receiving_flat_nfb_depth_mm` 讀取 `開關索引.csv` 或 nfbv5 數值資料的深度（例如士林 400=107，另一個來源型號可能是 68），不設第二套底板「深度」輸入。
- 走**同一** `receiving_base_plate_real_skins` 取得平面底板的真 T2 NFB 安裝皮面；`resolve_receiving_nfb_world_skin_datums` 對齊內門朝箱內 skin；`assembly_placement` 在單一 NFB 層時，以**箱體中心 X=0、該層 NFB 開孔高度 Y**及真實物理 skin 的 **Z** 定位；左右固定片再與已定位的底板固定孔貼合。換型號深度時，現行程式的**底板**可能按原型號深度變動；**固定片目標 Z 不得同步移動**，底板／固定片間若有深差則保持未驗證、不能放行，內門不動。
- **平底板兩顆不同型號**或**兩列**不能偷用最深一顆並聲稱全都貼合。若需要 PAD／其他實體底板，必須由其真實孔列及裝配來源驗證；缺項拒絕，不退回箱體後側 preview 冒充有來源的配置。
- 上述仍不代表大片固定片已擁有正式原圖 BEND。此固定片與側板兩側打標需獨立通過真實折向、物理接觸與回投影驗證後才准放行。

## 四之五、上下兩層分開建立真正 FinalScene 底板實體

`phase6_manufacturing_service.resolve()` 是組合 3D 的 `ResolvedManufacturingPart` 正式產生入口。已提交、來源唯一的外門上層 NFB 配置如有兩層，新增 `receiving_nfb_layer_physical_parts.expand_receiving_nfb_layer_parts`：

- 由既有 `receiving_nfb_layer_centers` 取得上下層各自的 NFB **Y 高度與螺絲孔 X 來源**及 `base_plate:nfb_layer:0/1` 來源身份；不可把 `slot_index`（同層第幾顆）冒充 `layer_index`（第幾層）。
- 每一層各自建立一個**新的** `BasePlatePartSpec`（原受電箱來源樣式和下料尺寸，不另造尺寸表）→ `build_part_render_data`，取得**兩個不同的真 FinalScene 材料、BEND 與 unfolded topology identity**；用**固定 X=0** 與該層孔群世界 **Y** 放置，移除單一根 `base_plate` 以免多畫一片。
- 原有 `base_plate` 可見性核選同時控制兩片來源實體。**板材成品高度由底板板件規格提供**，不被 330／830 的開孔高度覆蓋；外門下層不新增板件。
- **嚴格交付界限**：目前這是**兩個真實、身份分離的板材 FinalScene 源圖／3D 毛胚**，其 `metadata.manufacturing_ready=False`，`nfb_layer_manufacturing_status=NFB_TIER_BASE_EAR_AND_HOLES_UNVERIFIED`；尚未把每層實際 NFB 螺絲孔／全部耳片裝配孔製造結果接入新身份，也未完成每層獨立 Z 深度／左右固定片真折向、焊接貼合與側板 MARKING。兩片真實毛胚的出現**不是兩張已核准的製造圖**。不能以同一層原孔位鏡像到另一層或把第一層 CSV 深度套在第二層。

## 五、資料與向下相容

- 型號來源必須從 `基準檔/開孔/NFB/開關索引.csv` 或 V5 各品牌 `基準檔/開孔/NFB/數值規格/<品牌>/NFB數值規格.csv` **以被選中的 brand/model 查取深度**。不可從檔名尾碼或其他品牌推斷。
- 單層兩顆不同 NFB 的第二折尺寸，從**已提交之目前 Set/Bay** 的 NFBConfig 實際型號，配合該 Set `switch_brand` 的 CSV 深度求得。GUI `receiving_base_plate_values` 傳給**現有** `BasePlatePartSpec`／FinalScene，不額外建立第二種可編輯底板深度或品牌。
- Fold Designer 若尚未展開根層 NFB alias，只可使用**唯一 Set／唯一 Bay 的已提交資料**，或具身份匹配的指定當前 Set/Bay；多 Bay 未選或模型來源不符禁止跨箱套用。未提交／相同型號保持舊預覽，不能把 preview 33 當製造認證。
- UI 上未提交的深度配置不得回寫 Family 預設值；沒有明確配置時既有板件可維持預覽，但無憑證不得釋出 NFB 製造 DXF。
- **2026-10-26 更正**：本段早先主張「底板及固定片隨選用深度一起調 Z」已撤回；固定片改以全廠牌已知最大深度固定其 Z，同廠牌不同型號／不同層數不可移動。PAD 是另外的情形，不要拿尚未認證的墊高件替代雙折底板。

