# 2026-08-29 Assembly Collision / Registry Gate 驗證

## 範圍
本輪修正組合圖碰撞顯示假陰性、sub-tolerance 假穿透、OVERLAY 假二級／左右三角化非對稱，並建立 production registry 驅動的組合方式自動驗收矩陣。

## 自動測試
- `tests/test_assembly_collision.py`
- `tests/test_assembly_collision_integration.py`
- `tests/test_phase6_assembly_3d_view.py`
- `tests/test_phase6_assembly_intent_registry_matrix.py`
  - INSERT / OVERLAY / INSERT_OVERLAY × Head/Tail
  - pre-solve collision evidence
  - post-solve verified
  - corner topology stage count preserved
  - symmetric fixture mirror-equal
- `tests/test_phase6_assembly_registry_gui_matrix.py`
  - production registry 自動參數化
  - 2D / single 3D / assembly material equality
  - collision overlay segments > 0
  - Save / Reload stable
- `tests/test_phase6_shared_assembly_and_dimensions.py`
- `tests/test_phase6_corner_dimension_controls.py`
- `tests/test_phase6_return_2d_corner.py`
- `tests/test_phase6_3d_cutting_mesh.py`
- `tests/test_phase6_3d_view_regressions.py`

## Fresh results
- collision/backprojection/registry core: `80 passed, 2 skipped`
- registry GUI matrix: `3 cases passed`；另以 INSERT / OVERLAY / INSERT_OVERLAY 三個獨立 xvfb GUI smoke 程序重跑，三者皆正常 exit 0
- shared assembly/dimension: `33 passed`
- corner dimension controls: `7 passed`
- return 2D: `1 passed`
- 3D cutting mesh: `8 passed`
- 3D view regressions: `5 passed`

## 實檔
### 自訂(9).p6fold / INSERT
- Head verified = True
- Tail verified = True
- relief errors = `{}`
- collision overlay = True / 170 segments
- Head/Tail assembly corner = `38×27`
- main 2D vs assembly symmetric-difference = 0
- main 2D vs single 3D symmetric-difference = 0
- Save/Reload material diff = 0

### 自訂(10).p6fold / INSERT_OVERLAY
- Head verified = True
- Tail verified = True
- relief errors = `{}`
- collision overlay = True / 198 segments
- canonical corner = `40×23 + 16×4`（先前 16×23 + 14×4 為錯誤 solver 候選，已廢止）
- main 2D vs assembly symmetric-difference = 0
- main 2D vs single 3D symmetric-difference = 0
- Save/Reload material diff = 0

### OVERLAY symmetric GUI fixture
- Head/Tail verified = True
- collision overlay = True / 122 segments
- no invented secondary stage
- mirrored side measurements equal (`25×11.482` on the tested lower/upper mating row)
- 2D vs single3D vs assembly symmetric-difference = 0

## 舊測試債務說明
完整舊 test suite 含已知 stale contracts。抽查的 `test_gui_production_imports_ae_engine_not_legacy_core_modules` 與舊 corner-lock test 在上一個 `064513` 基準包即同樣失敗，因此未為了把歷史 suite 湊成全綠而修改與本輪無關的正確程式。


## 最終交付封包
- FULL：`PHASE6_ASSEMBLY_COLLISION_REGISTRY_GATE_FULL_20260829_075946.zip`
- UPDATE：`PHASE6_ASSEMBLY_COLLISION_REGISTRY_GATE_UPDATE_20260829_075946.zip`
- UPDATE 僅包含相對 `064513` 基準的 18 個差異檔，不含 `config.ini`。
- 封包完成後必須實際解壓並逐檔 SHA256 比對來源。
