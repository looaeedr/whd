# Phase6 交付備忘 — OVERLAY 成型 FW Registry / 3D Relief 正式化

> 本檔只是交付歷史備忘，不是 release policy、runtime oracle、必備檔名契約或下一輪修改的 Source of Truth。
> 正式依據請以 `AGENTS.md` 的 Phase6 Knowledge Preflight、`release_required_artifacts.json`、`AI_HANDOFF.md`、`CONTEXT.md`、對應 spec / verification 與踩坑庫為準。
> 不得因本檔存在或檔名固定，就把 `DELIVERY_README.md` 照搬成其他流程的 mandatory artifact。

## [CURRENT] 2026-09-02 Runtime semantic guard

- `OVERLAY = 貼外`。
- `包覆貼外 = 高階 preset`；`WRAP = 下方局部包覆 Joint`；**包覆貼外 ≠ OVERLAY ≠ WRAP**。
- Receiving EndCap D core = `D - 2T`。
- Vault EndCap D core = `D - 3T`。
- Active standard OVERLAY rule：`ENDCAP_TOP_OVERLAY_STANDARD_V1@3`，正式公式以 STANDARD + semantic delta 為 Source of Truth：`primary_u = side_fold + FW`、`primary_v = ytop1 + FW - T`、`secondary_u = side_fold`、`secondary_depth = T`。fixture `T=2 / side_fold=15 / FW=25 / ytop1=16` = **`40×39 + 15×2`**。
- `formed FW` 只保留作 3D shadow / collision evidence，**不得作 runtime CUTTING oracle**，也不得回寫 EndCap material FW。
- **`40×23 + 16×4` 只屬 linked-FW `INSERT_OVERLAY` fixture**（`ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1@1`），不是標準 OVERLAY oracle。


> 本文件其餘日期段落是交付歷史；除標成 `[CURRENT]` 外，只能作 HISTORICAL/FIXTURE evidence，不可作 runtime oracle。

### [HISTORICAL/SUPERSEDED — 不可作 runtime oracle] 2026-08-29 formed-FW v2 交付記錄

- 使用者實檔 `金庫型貼外.p6fold`：W=400 / T=2 / nominal FW=25 / OVERLAY。
- 箱身 Fold Profile 折後 formed FW occupation=29；上方每側 X CUT=29，單側 `29+371=400`，左右後中央 342。
- EndCap 自身 FW 仍是 25，上方 V 仍為 39；不得把 formed FW=29 回寫 EndCap FW。
- 下方 CROSS / EXTRA_CUT / WIDTH / 1.5T 維持每側 3、中央 394。
- Certified Registry `ENDCAP_TOP_OVERLAY_STANDARD_V1@2` 明確宣告 `BOX_BODY_FORMED_FW`，X formula=`primary_u=mating_width`；29 不硬寫進 rule。
- 3D solver 保存 formed-FW geometry evidence 並 shadow validate；Head/Tail post-solve residual penetration=0。
- persistence 升 `relief_contract_version=2`；舊 revision-1/versionless 40-mm committed relief 在 fresh load 時失效，不得重播。
- 2D / single3D / assembly / Save→Reload 共用 canonical resolved manufacturing geometry。
- 歷史 `40/320` 與 `25/350` 都已 superseded，不再是現行回歸真值。

---
# [SUPERSEDED AS COMPLETE CONTRACT] Phase6 交付說明 — OVERLAY 下方 relief basis 364→394 修正

- `金庫型貼外.p6fold`：OVERLAY / W=400 / T=2 / FW=25。
- 歷史當時只確認下方改為每側 3、剩寬 394；當時所寫上方 40/320 已被 formed-FW 29/342 契約推翻。
- 根因不是 1.5T 數值，而是 flat-X 的 nominal side basis 被錯套到下方 CROSS。
- 2D、單板 3D、組合圖、Save→Reload 實檔材料一致。
- 新增 OVERLAY relief basis Skill、回歸測試與 AI/SOP 踩坑規則。
- `config.ini` 不修改。

---
# Phase6 交付說明 — 組合圖 Joint 診斷雜訊隔離修正

## 本輪修正（2026-08-29）
- 修正 WRAP / Joint Registry 開發診斷資料誤進正式「組合圖」：移除操作員畫面的 `Joint` 下拉與 Registry / preserve / relief / pre-post 長狀態字串。
- 正式組合圖不再接收 `joint_diagnostics` / `selected_joint_id`，因此開發用 contact / penetration / preserve / relief 線段與方向箭頭不會再成為操作圖層。
- Joint Registry、AssemblyJoint、WRAP、3D collision solver 資料仍完整保留在 canonical resolved geometry，僅與正式操作畫面隔離，沒有砍掉求解功能。
- 同步修正 WRAP 後既有單板 3D 回歸：Door / Base Plate 等未參與 USER_ADDED Joint 的獨立板件不再被強制拖進整櫃 assembly solve；箱身、封頭、封尾與實際參與 USER_ADDED Joint 的板件仍使用 canonical resolved assembly geometry。
- `config.ini` 不修改。

## 使用者實檔驗證
- `金庫型.p6fold`：existing_parts 僅 `box_body / head / tail / door / base_plate`。
- 檔內 4 筆 `LEGACY_MIGRATED` Joint 保留為內部組合語意，不再生成正式組合圖的 Joint 控制項或診斷圖層。
- 實際 Tk 載入檢查：`ACTUAL_P6FOLD_OPERATOR_UI_CLEAN=PASS`。

## Fresh 驗證
- Assembly / Joint / Collision / Resolved Manufacturing 核心：`126 passed`。
- 最新 3D layout：`11 passed`；Registry GUI matrix：`3 passed`；Registry form/shadow GUI：`8 passed`。
- Assembly render / dimension / cutting：`66 passed`；其他現行 3D renderer/operator focused gate：`48 passed`。
- Project / Save / Reload headless gate：`28 passed, 9 display-dependent skipped`。
- 舊 Corner/UI 契約組與 20:45 原包同為 `18 failed / 70 passed`，沒有新增失敗；舊 Designer/3D 契約組由原包 `21 failed / 145 passed` 改善為 `20 failed / 146 passed`。

## 本輪封包
- FULL：`PHASE6_ASSEMBLY_VIEW_JOINT_DEBUG_CLEAN_FULL_20260829_211125.zip`
- UPDATE：`PHASE6_ASSEMBLY_VIEW_JOINT_DEBUG_CLEAN_UPDATE_20260829_211125.zip`
- FULL / UPDATE 共用 Asia/Taipei 完整時間戳；UPDATE 不含 `config.ini`。

---
# Phase6 交付說明 — Assembly Collision Registry Gate

## 本輪最終交付（2026-08-29）
- 修正組合圖碰撞假陰性：顯示 solver 前的 pre-solve collision probe，不再拿已切除後 final material 判斷。
- 修正 sub-tolerance sliver fallback 假穿透。
- INSERT / OVERLAY / INSERT_OVERLAY 均維持合法 corner topology；solver 只收斂尺寸，不可憑空新增／刪除級數。
- 真正鏡像對稱時消除 triangle tessellation 左右漏採樣；非對稱件不強制鏡像。
- `自訂(9)` INSERT 仍為 38×27；`自訂(10)` INSERT_OVERLAY Head/Tail verified，碰撞紅區可見。
- production registry 自動驅動未來新增組合的 Head/Tail、碰撞、零穿透、2D/單板3D/組合、Save/Reload 驗收。

## Fresh gate
- collision/backprojection/registry core：`80 passed, 2 skipped`。
- dimensions / cutting mesh / 3D view：`51 passed, 2 skipped`。
- return-to-2D：`1 passed`。
- registry GUI smoke：INSERT / OVERLAY / INSERT_OVERLAY 三個獨立程序皆 PASS 且正常 exit 0。
- `38×27` regression + `自訂(10)` INSERT_OVERLAY regression：`2 passed`。
- `config.ini` SHA256 與 `064513` 基準完全一致。

## 本輪封包
- FULL：`PHASE6_ASSEMBLY_COLLISION_REGISTRY_GATE_FULL_20260829_075946.zip`
- UPDATE：`PHASE6_ASSEMBLY_COLLISION_REGISTRY_GATE_UPDATE_20260829_075946.zip`
- UPDATE 不含 `config.ini`。

---
# Phase6 交付說明 — EndCap 單級 INSERT 38×27 / 三視圖同步 / 文件補齊

## 本輪變更（2026-08-29）
- `自訂(9).p6fold` 封頭／封尾上方單級 INSERT 修正為實際 `38×27`。
- 修正 normal ±T/2 skin contact 被誤判為 penetration，避免 38 被求成約 38.98→39。
- 防止單板 3D 退回 legacy `40×27`；主 2D、單板 3D、組合圖、尺寸文字全部共用 canonical Manufacturing material。
- 延續本輪 UI：全螢幕旁 `回2D截角`、組合圖左側全部板金截角尺寸、各板件組合顯示勾選、每片板件 2D/3D 自身截角尺寸。
- 補齊修改日誌、Superpowers verification、AI/SOP、handoff、context、交付說明與目前任務；文件與程式同版交付。

## Fresh 驗證
- `自訂(9)`：Head/Tail `verified=True`、`errors={}`；左右角皆 `38×27`；2D vs assembly symmetric difference = 0。
- focused regression：`46 passed / 0 failed`。
- `38×27` 是本實檔幾何 regression evidence，不是硬編碼公式。
- `config.ini` 不修改。

## 本輪封包
- FULL：`PHASE6_ENDCAP_RELIEF_38_SYNC_DOCS_FULL_20260829_064513.zip`
- UPDATE：`PHASE6_ENDCAP_RELIEF_38_SYNC_DOCS_UPDATE_20260829_064513.zip`
- FULL / UPDATE 共用 Asia/Taipei 完整時間戳。

---
# Phase6 交付說明 — 3D UI 永久控制區重排

## 本輪變更（2026-08-24）

- 3D 開啟後直接進入箱身，移除首頁 landing UI。
- 置頂區永久顯示 `檔案 ▼`、全域設定、3D 顯示設定、還原初始值、取消、確定。
- `檔案 ▼` 收合開啟／儲存／另存新檔；檔案操作語意與 ProjectSession committed/draft 規則不變。
- 左側 `板件 ▼ / 新增 ▼ / 刪除` 固定同列且切換板件不消失。
- 右側 3D 上方 `結構 ▼ / 組合方式 ▼ / 參數鎖定` 永久顯示；結構、組合方式不受參數鎖控制。
- 參數鎖定時不顯示右側參數面板；解鎖後顯示結構參數與進階參數。
- 3D 內固定選項型 readonly Combobox 改為 `Menubutton + Menu`；Entry 不變。
- 3D UI 移除 `輸出 STOCK` 選項；製造資料模型未因此改寫。
- `config.ini` 不修改。

## 本輪驗證

- `python -m compileall -q ...` 通過。
- 完整 Tk 回歸：`418 passed, 2 skipped, 4 deselected, 0 failed`。
- 4 個 deselected 為基準包既知缺少 `/mnt/data/自訂.p6fold` 的外部 fixture。
- `config.ini` SHA256：`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`，與基準包完全相同。
- 受電箱 Family／Fold Profile／EndCap／manufacturing 檔案與本輪基準逐位元一致。

## 基準

- `PHASE6_RECEIVING_BOX_2D_PHASE1_FULL_20260824_003600(1).zip`

---

# Phase6 交付說明 — FW 連動 BUG 修復

## 最新修復

- 修正箱身對稱 Fold Chain 使用列索引造成 FW/D/Z 錯欄連動；結構列改按 `phase6_key`／折彎邊界語意配對。
- 封頭／封尾 FW 改為四態控制權：`FOLLOW_BODY / FOLLOW_HEAD / FOLLOW_TAIL / INDEPENDENT`。
- 先改封頭會帶封尾、先改封尾會帶封頭；再改另一端後兩端各自獨立；重新提交箱身 FW 時箱身重新接管兩端。
- 封頭／封尾 FW 可直接輸入，不再靠鎖欄位維持資料一致性；非數字暫態輸入不改控制權。
- 主 GUI、3D Fold Designer、2D/3D resolved geometry 與 `.p6fold` 共用同一 FW 狀態。
- `config.ini` 不修改。

## 既有交付基準與功能


## 本輪基準

- 基準完整包：`PHASE6_HOLE_EDITOR_CANVAS_VIEW_FULL_20260823_160603 (1).zip`
- 本輪開發以該包為唯一基準；舊設定面板包不再沿用。
- `config.ini` 不修改。

## 本輪完成

- 新增箱身正式結構型態 Source of Truth：
  - 一體成型
  - 二件式（W 二分）
  - 三件式（W 三分）
  - 三件式（側背分離）
- 型態預設鎖定；箱身頁解鎖後可切換，且各型態 configuration 獨立保留。
- 二件式只拆中央 W；W 左／右雙向補全、單側最小 50 mm、系統自算可保留 0.5 mm。
- 中央接合折邊為一般 90° BEND：預設 12 mm、最小 12 mm、>=50 mm 只警告不阻擋。
- 封頭／封尾端部十字截角：各自使用實際 `ybottom1`，共用可調 `+5 mm` 與 `0.5T` 單邊留肉。
- 底板只在 resolved seam 真正交會時產生局部十字避讓；預設總長 20 mm、單邊留肉 0.5T。
- W 三分預設 `50 / (W-100) / 50`，左右連動，中間可直接驅動。
- 側背分離：左右側板成型 D、後側折邊預設 15 mm；後面板成型寬 `W - compensation`，補償預設 0.5T；3D 組裝後 W/D envelope 不得向外擴張。
- 開孔不因分件重新排位；跨 seam feature 依每片實際 material boundary 做 operation-aware clipping，CUTTING／BLIND_HOLE／MARKING／DATUM 保持各自 process layer。
- 2D exploded FinalScene、3D 組裝、獨立 DXF export 共用同一 resolved physical pieces。
- 箱身頁 GUI：鎖定時只顯示摘要；解鎖後顯示型態參數；「截角／避讓」預設收合；側背分離顯示唯讀 D。
- warning fact 同步供設定面板、2D、3D 顯示，warning UI state 不持久化。
- Code-audit hardening：corrupt/direct-API W state fail closed；legacy `.p6fold` 缺 structure state/lock 走一次性 migration；0.5T 留肉重用既有 CROSS/RETAIN 語意。
- 已設定 W 分件後再修改總 W：在 GUI commit seam 依最後 driver 正常補全；若新 W 無法形成合法分件則 reject/revert，不弱化 resolver。

## 最終驗證

- 箱身結構專項（含 audit contract 與真實 Tk GUI）：`38 passed`。
- 完整回歸（排除 4 個既知外部 fixture）：`407 passed, 2 skipped, 4 deselected, 0 failed`。
- 原始 `160603` 基準包單跑該 4 項同樣 `4 failed`，全部是 `/mnt/data/自訂.p6fold` 不存在，非本輪回歸。
- `python -m compileall -q .` 通過。
- `config.ini` SHA256：`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`，與原始基準相同。

## 文件

- `CONTEXT.md`
- `docs/superpowers/specs/2026-08-23-phase6-box-body-structure-buildable-spec.md`
- `docs/superpowers/verification/2026-08-23-phase6-box-body-structure-verification.md`
- `使用說明書.md`
- `修改日誌/20260823.md`

## 本輪封包

- FULL：`PHASE6_FW_LINK_BUGFIX_FULL_20260823_212355.zip`
- UPDATE：`PHASE6_FW_LINK_BUGFIX_UPDATE_20260823_212355.zip`
- FULL / UPDATE 共用 Asia/Taipei 完整時間戳：`20260823_212355`。
- UPDATE 不含 `config.ini`。

## 2026-08-29 — Assembly Collision Registry Gate
- 修正組合圖「實際有碰撞卻顯示未偵測」：碰撞紅區改讀 solver 前 pre-solve Head/Tail probe。
- 修正 sub-tolerance sliver 被 fallback 復活成假穿透。
- `OVERLAY` 不再跳過 topology normalization；單級角不會長出微小假二級。
- 真正鏡像對稱的組合幾何會用 geometry symmetry 判定消除 triangle tessellation 左右漏採樣；非對稱件不強制對稱。
- 新增 registry-driven assembly gate；任何未來新增 `BOX_ASSEMBLY_TYPE_IDS` intent 都會自動進 Head/Tail、collision、topology、2D/3D/assembly、Save/Reload 驗收。
- 實檔：`自訂(9)` INSERT 保持 38×27；`自訂(10)` INSERT_OVERLAY Head/Tail verified 且碰撞紅區可見。

## 2026-08-29 Certified Relief Registry 第一階段
- 新增已認證截角公式資料庫。
- 首筆規則 `ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1` 保護 linked-FW INSERT 的 38×27 類結果。
- 3D solver 對 CERTIFIED 規則只做 shadow validation，不再覆蓋已知正確公式。
- OVERLAY / INSERT_OVERLAY 尚未升格為全量 certified，仍依既有 fallback 與 registry gate 驗證。

### Certified Registry 本輪驗證補充
- `自訂(9).p6fold`：Head/Tail 皆命中 `ENDCAP_TOP_INSERT_STRUCTURAL_CONTACT_V1`，輸出 38×27，collision overlay 170 段。
- `自訂(10).p6fold`：linked-FW INSERT_OVERLAY 已命中 `ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1@1` / CERTIFIED；正確 fixture 為 40×23 + 16×4。
- 標準 GUI matrix：INSERT / OVERLAY / INSERT_OVERLAY 全部 PASS；其中標準 INSERT 仍含 `ytop1` row，所以不套 linked-FW INSERT certified rule。

## 2026-08-29 13:16 Certified Relief Registry 完整化交付

本版完成金庫型／受電箱固定截角資料庫化，以及已知 EndCap Assembly Intent 公式的 certified-first 架構。正式規格：`docs/superpowers/specs/2026-08-29-certified-relief-registry-design.md`；任務清單：`docs/superpowers/plans/2026-08-29-certified-relief-registry-implementation.md`。

預定封包：
- `PHASE6_CERTIFIED_RELIEF_REGISTRY_COMPLETE_FULL_20260829_131622.zip`
- `PHASE6_CERTIFIED_RELIEF_REGISTRY_COMPLETE_UPDATE_20260829_131622.zip`

交付基準：`PHASE6_CERTIFIED_RELIEF_REGISTRY_FULL_20260829_082214.zip`。UPDATE 只收錄相對該基準的真實差異檔；禁止包含未修改的 `config.ini`。Fresh verification 詳見 `docs/superpowers/verification/2026-08-29-certified-relief-registry.md`。


## [HISTORICAL/FIXTURE — 不可作 runtime oracle] 2026-08-29 13:39 Certified Relief Registry 交付記錄

- 已完成金庫型／受電箱固定截角資料庫化。
- 已完成標準 INSERT / OVERLAY / INSERT_OVERLAY 與 linked-FW INSERT / linked-FW INSERT_OVERLAY 的 certified-first 規則。
- CERTIFIED / CERTIFIED_FROM_3D 命中後，3D 只做 shadow validation；registry MISS 才允許 fallback。
- ambiguity fail-closed；ENGINE_CONFLICT 不覆蓋 certified canonical；Save/Reload 保存 rule_id / revision / trust_level；Promotion UI 只建立候選 manifest。
- Fresh gate：Registry/collision `87 passed`；Registry GUI `3 passed`；3D/dimensions/return-to-2D `38 passed`；project/receiving `29 passed`，另 2 條 stale receiving GUI test 在本版與 `082214` 基準包同樣失敗，非本輪退化。
- 實檔：`自訂(9)` = CERTIFIED `38×27`；`自訂(10)` = CERTIFIED `40×23 + 16×4`；兩者 Save/Reload metadata 與 canonical material 一致。
- `config.ini` SHA256 與基準完全相同。

最終封包：
- `PHASE6_CERTIFIED_RELIEF_REGISTRY_COMPLETE_FULL_20260829_133925.zip`
- `PHASE6_CERTIFIED_RELIEF_REGISTRY_COMPLETE_UPDATE_20260829_133925.zip`

封包 completion gate：FULL / UPDATE 必須實際解壓到全新目錄，逐檔 SHA256 與目前來源工作樹一致；完成後才視為正式交付。


### 最終封包 Completion Gate
- FULL：681 個檔案。
- UPDATE：28 個真實差異檔；`config.ini` 不在 UPDATE。
- 第一輪實際解壓 SHA256：FULL 681/681、UPDATE 28/28 全部與來源一致，0 missing / 0 mismatch / 0 extra。
- FULL / UPDATE `unzip -t` 均無壓縮錯誤。
- 任務清單已全部勾選完成；文件關閉後以同時間戳重封，交付前再次解壓逐檔驗證。


## 2026-08-29 15:xx — INSERT 單級拓撲與 linked-FW C04 修正

- 純 `INSERT` 與 `OVERLAY` 是**單級截角**；資料模型現在會強制清除任何殘留 `secondary_retain_t` / `secondary_depth_t`。
- Certified Registry 增加 topology boundary validation：`INSERT` / `OVERLAY` 規則若回傳二級 geometry，直接拒絕，不得成為 canonical material。
- 撤銷錯誤的 linked-FW `INSERT_OVERLAY` 推導 `16×23 + 14×4`。既有 2026-08-21 C04 製造契約明確規定第二級 CUTTING = `side_fold + 0.5T`；第一級 X = `side_fold + FW`。
- 因此 T=2、side_fold=15、FW=25、無獨立 ytop1 的 linked-FW fixture 正確為 **`40×23 + 16×4`**。有 ytop1=16 的標準 C04 fixture 為 **`40×39 + 16×4`**。
- `ENDCAP_TOP_INSERT_OVERLAY_LINKED_FW_V1` 信任等級改為 `CERTIFIED`，證據來源改為既有 C04 製造規格，不再以錯誤 3D 候選升格。
- 實際 `自訂(10)` 切換為純 INSERT 後：Head/Tail = **38×27，secondary=None**；Save/Reload 後仍保持單級。

## 2026-08-29 15:xx 最終 fresh gate

- INSERT/C04/registry/collision/endcap affected suite：105 passed；另 1 條 `test_stretched_export_passes_fw_and_tail_to_geometry_loader` 已用上一版 133925 基準 fresh 對照，基準本來就同樣 TypeError，非本次退化。
- FinalScene / 3D / corner dimensions：57 passed。
- Registry GUI matrix：3 passed（INSERT / OVERLAY / INSERT_OVERLAY）。
- Project / Save-Reload / corner UI（xvfb）：32 passed。
- `自訂(10)` 原 INSERT_OVERLAY：40×23 + 16×4，Head/Tail CERTIFIED，shadow residual=0，2D vs assembly diff=0，Save/Reload 保留 rule/revision/trust。
- `自訂(10)` 切純 INSERT：38×27 單級，secondary=None；raw state 無 secondary_*，Save/Reload 後仍單級。

## [HISTORICAL/SUPERSEDED — 不可作 runtime oracle] 2026-08-29 OVERLAY 中間修正
- 撤銷錯誤值 `25×39`：它來自把 flat-X 的有效 X BEND=0 誤用成截角名義側折=0。
- **歷史中間結論（已 superseded）**：曾把 nominal side fold 加進 flat-X，得到 40×39。現行上方 X 必須依 Box Body formed FW，該 W400/T2/FW25 fixture 為 29×39。
- 新增 nominal-fold metadata 與 registry 防退化測試；2D/3D/assembly 共用同一 canonical material。
- `自訂(9)` 38×27 與 `自訂(10)` 40×23+16×4 均 fresh 回歸無退化。

### OVERLAY 修正 fresh gate
- 大型 affected suite：198 passed / 2 skipped；另 6 條 exporter/headless 舊契約已用上一版 `152212` FULL fresh 對照，基準原本即同樣失敗，非本次退化。
- 2 條 DISPLAY 3D GUI 測試以 xvfb 重跑：2 passed。
- Registry GUI matrix：3 passed。
- [HISTORICAL/SUPERSEDED — 不可作 runtime oracle] 當時 OVERLAY 真 GUI 曾為 Head/Tail 40×39；該 v2 formed-FW contract 本身也已被 `ENDCAP_TOP_OVERLAY_STANDARD_V1@3` supersede。
- `自訂(9)`：INSERT 38×27；`自訂(10)`：INSERT_OVERLAY 40×23+16×4；兩者 Head/Tail verified、2D vs assembly diff=0、Save/Reload rule metadata 一致。


## 2026-08-29 WRAP / AssemblyJoint / Registry v2 / 3D Solver v2 完成

- 新增 Global `AssemblyJoint`：INSERT / OVERLAY / INSERT_OVERLAY / WRAP。WRAP 的 subject 為外包者、target 為被包覆者。
- 同一 Part 可同時存在 Intent-derived Joint 與 USER_ADDED WRAP；切換 Intent 不刪 USER_ADDED Joint。
- Certified Relief Registry 升級為外部 JSON + Joint Signature + Safe Formula Evaluator + candidate/promotion revision 流程。
- GUI 新增「截角資料庫」與「組合 Joint」表單；candidate-specific 3D evidence 才能 Promotion。
- 3D Solver v2：legal contact / illegal penetration、preserve / relief ownership、generalized backprojection、topology fitter fail-closed、candidate replay zero-penetration。
- Canonical `ResolvedManufacturingGeometry` 已供 2D / Single3D / Assembly3D / FinalScene / DXF 共用。專案目前沒有 production NC sink，因此沒有新增假 NC exporter。
- Save/Reload 保存 Joint Graph、USER_ADDED WRAP、rule_id / revision / trust_level / joint_signature；legacy migration 不猜 WRAP。
- Fresh regression：61 + 54 + 7 + 118 全部 PASS。
- [HISTORICAL/FIXTURE] 自訂(9)=38×27 INSERT；自訂(10)=40×23 + 16×4 INSERT_OVERLAY。這些是 fixture evidence。當時的 formed-FW OVERLAY contract 已 superseded，**不得作 runtime oracle**；現行標準 OVERLAY 由 `ENDCAP_TOP_OVERLAY_STANDARD_V1@3` 決定。


## 2026-08-29 — Release Integrity Gate

UPDATE 不再只依 hash diff 收檔。為避免把新 UPDATE 套到較舊工作樹時遺失早期新增的驗收測試，`release_required_artifacts.json` 所列 mandatory verification artifacts 必須每一包 UPDATE 都重複收錄。若任一 mandatory 檔不存在，打包流程必須 fail closed。

本輪已 fresh 驗證：Assembly Intent registry matrix 18 passed；Assembly registry GUI matrix 3 passed；release integrity gate 3 passed。
