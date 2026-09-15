# 2026-08-30 受電箱 Family / WRAP / Blank 漂移 / 組合區 Follow-up 驗證

## 使用者回報

1. 3D 內切換「受電箱」沒有同步成 `W=800 / H=1600 / D=350`。
2. 封頭沒有常駐可選的「下方外側包覆」。
3. Head/Tail 每切換一次，展開料會再增加約 2 mm。
4. 組合體左側輸入／板件區被固定高度切出一塊，沒有使用全部剩餘空間。
5. 組合體左側仍殘留帶標題的「組合圖板件 / 截角尺寸 / 展開料」LabelFrame 旗標／框。

## 根因

- `ae_engine/cabinet_types/receiving.py` Family defaults 漏掉 `h=1600`；3D baseline-model handler 只改 topology，未把 Family W/H/D 提交到 live globals / editor state。
- 下方 WRAP 已有 domain state 與 Registry，但啟用開關只存在於參數解鎖頁，鎖定時操作員看不到。
- Receiving EndCap D 核心正式契約是 `D - 2T`，但 `read_endcap_xy_profiles()`、live `_sync_active_endcap_and_global_whd()`、`_propagate_endcap_derived_cores()` 仍混有 Vault `D - 3T` 假設；Head/Tail 切換時把材料核心反推回全域 D，造成每次約 `+1T` 漂移。
- Family 切換後 `merge_box_body_profile()` 保留前一 Family 的外側 fold topology，使 Vault `zr1` 可滲回 Receiving；Receiving topology 必須在 merge 後再次套 Family transform。
- 組合板件 Canvas 與其 parent 使用固定高度 / `fill=X`，因此左側剩餘空間未被利用。
- 即使改成 `expand=True`，外層仍是帶標題的 `ttk.LabelFrame`，視覺上仍切成獨立「組合圖」旗標區塊。

## 修正契約

- 切換「受電箱」是完整 Family transaction：live W/H/D、settings snapshot、box-body editor 與 Family structure 同步切到 `800 / 1600 / 350`。
- Receiving lower WRAP 啟用選擇在 Head/Tail 常駐控制列可見；`reserve_u / reserve_v` 仍保留在參數解鎖區。
- Receiving EndCap depth compensation 的唯一係數為 Family policy `endcap_depth_comp_t() == 2T`；profile read、derived-core propagation、live global sync 不得各自硬寫 3T。
- Head/Tail 反覆切換不得改變 global D，也不得改變未編輯的 canonical blank size。
- Receiving box-body profile merge 後仍須套 `transform_box_body_profile()`，禁止舊 `zr1` 回灌。
- 組合體左側板件／輸入區使用 `fill=BOTH + expand=True`，Canvas 不再用固定 190 px 高度。
- 組合體左側不再建立帶標題/框線的 `LabelFrame`；改用普通 `ttk.Frame` 直接承接可捲內容，整塊剩餘空間就是輸入／板件區。

## 新增 / 更新回歸

- `tests/test_phase6_receiving_followup_20260830.py`
  - Family defaults = 800×1600×350。
  - live Family switch 同步 globals + persistent WRAP control。
  - Head/Tail 來回切 10 次，D / blank 不漂移。
  - assembly left input area 使用全部剩餘高度。
  - assembly mode 不得存在獨立帶標題的 LabelFrame 旗標。
- `tests/test_receiving_cabinet_type.py`
  - Menubutton selector 依正式 Menu contract 驗證，不再使用已淘汰 Combobox `values`。
  - live Receiving fold chain 不得殘留 `zr1`。
- `tests/test_receiving_cabinet_2d.py`
  - Receiving Family H default 正式鎖定 1600。

## Fresh 驗證（開發工作樹）

- `tests/test_phase6_receiving_followup_20260830.py`：5 passed。
- Receiving Family / lower WRAP / follow-up 合併：40 passed。
- Latest layout contract：11 passed。
- 3D view + shared assembly dimensions + OVERLAY：45 passed。
- Box-body structure：20 headless passed + 5 real Tk passed。
- Collision / Joint / Certified Registry core：101 passed。
- `.p6fold` Project Save→Reload：9 passed + 10 passed = 19 passed。
- canonical `config.ini` SHA256：`5947c847ab96a6d739d464d75f50457300ac2cd240e232eb0f2fe1d53c41683d`，未修改。

## Release Gate

正式 FULL / UPDATE 必須使用新的 Asia/Taipei `YYYYMMDD_HHMMSS` 時間戳；UPDATE baseline 固定為 `PHASE6_FW_LINK_BUGFIX_FULL_20260823_212355(3).zip`，且 UPDATE 不得包含 `config.ini`。新回歸與本驗證文件必須列入 cumulative UPDATE mandatory artifacts。重封後仍須 freshly extract FULL，再跑 Receiving follow-up、Registry/OVERLAY、結構與 Save→Reload smoke。
