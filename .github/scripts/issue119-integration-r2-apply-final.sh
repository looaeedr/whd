#!/usr/bin/env bash
set -euo pipefail

PROD=40620c516ad099911ebd22c928237f81641759f2
OLD=7f894432ed7b4b4cdcd2160031c2f47e712cf436
AI_FILE='個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md'
STATE_FILE='docs/superpowers/verification/2026-09-12-issue119-replay-state.md'

git config user.name "looaeedr"
git config user.email "76246585+looaeedr@users.noreply.github.com"
git fetch origin cleanup/2d-3d-sync fix/issue119-replay-latest-20260912-r1
test "$(git rev-parse origin/cleanup/2d-3d-sync)" = "$PROD"
test "$(git rev-parse origin/fix/issue119-replay-latest-20260912-r1)" = "$OLD"
test "$(git merge-base HEAD origin/cleanup/2d-3d-sync)" = "$PROD"
echo "PROD=$PROD"
echo "OLD_ACCEPTED=$OLD"

sudo apt-get update -qq
sudo apt-get install -y -qq xvfb
python -m pip install -q -r requirements.txt pytest matplotlib

sha256sum config.ini > /tmp/config.before
LC_ALL=C find 基準檔 -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/baseline.before
git diff --check
test -z "$(git ls-files --others --exclude-standard)"

set +e
git merge --no-commit --no-ff origin/fix/issue119-replay-latest-20260912-r1
rc=$?
set -e
if [ "$rc" -ne 0 ]; then
  mapfile -t unresolved < <(git -c core.quotePath=false diff --name-only --diff-filter=U)
  test "${#unresolved[@]}" -eq 1
  test "${unresolved[0]}" = "$AI_FILE"
  git checkout --ours -- "$AI_FILE"
fi

python - <<'PY'
from pathlib import Path
p = Path('個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md')
marker = 'Issue119 Corner Data lifecycle/readability'
block = '''

## 2026-09-12 — Issue119 Corner Data lifecycle/readability
- 症狀「切板件後截角資料收不回去」的典型根因是：**只藏右側 canvas、左側 panel 仍 managed**；enter/exit 必須對稱處理完整 widget lifecycle。
- family 切換時不要在 topology 尚未 commit 前刷新 UI；必須等 **authoritative topology commit 完成後才刷新 visible projection**，再讀 post-commit `available_parts`。
- **同一 transaction 只能有一次 refresh owner**；重播 patch 時要用 contract test 防止 duplicate refresh block。
- Corner Data 不可沿用一般 2D 的 **175px generic annotation gutter**；它有獨立 operator-info row，應用 dedicated compact viewport。
- 以上只修 View/readability；validation 只判對錯，不得把量測值或 fit ratio 回灌 manufacturing geometry。
'''
text = p.read_text(encoding='utf-8')
if marker not in text:
    p.write_text(text.rstrip() + block + '\n', encoding='utf-8')
PY

git add -- "$AI_FILE"
test -z "$(git -c core.quotePath=false diff --name-only --diff-filter=U)"
grep -q 'INVARIANT_MANIFEST_CANONICAL_PATH_HASH' "$AI_FILE"
grep -q 'Issue119 Corner Data lifecycle/readability' "$AI_FILE"

git -c core.quotePath=false diff --name-only "$PROD" | sort > /tmp/changed.txt
cat > /tmp/expected.txt <<'EOF'
.agents/skills/engineering/截角資料入口收斂/SKILL.md
.github/scripts/issue119-integration-r2-apply-final.sh
.github/workflows/issue119-integration-r2-apply-final.yml
.github/workflows/issue119-integration-r2-merge-probe.yml
docs/superpowers/verification/2026-09-12-issue119-replay-state.md
fold_designer_bridge.py
gui.py
tests/test_issue119_corner_data_knowledge_contract.py
tests/test_issue119_corner_data_transition_ui.py
個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
EOF
sort -o /tmp/expected.txt /tmp/expected.txt
diff -u /tmp/expected.txt /tmp/changed.txt
test -z "$(git -c core.quotePath=false diff --name-only "$PROD" -- config.ini 基準檔 ae_engine phase6_fold_profiles.py phase6_endcap_semantics.py)"

cat > /tmp/evidence.md <<'EOF'
執行開發任務
寫技能
截角資料入口收斂
phase6-corner-3d-model-integrity
phase6-release-packaging
phase6-gui-performance-integrity
diagnosing-bugs
tdd
驗證板件與DXF
monitoring-remote-qa
UI設計與去AI味
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/08_WHD技能建立與修改規則.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/continuous_execution_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/踩坑庫/phase6_assembly_relief_pitfalls.md
READ_REFERENCE: 個人AI檔案庫/第二層_專案與SOP/04_WHD鈑金展開幾何引擎規範.md
READ_REFERENCE: 基準檔/截角資料庫/README_母規則說明.md
READ_REFERENCE: 基準檔/截角資料庫/certified_relief_rules.json
READ_REFERENCE: release_required_artifacts.json
EOF
python tools/phase6_skill_preflight.py \
  --task "整合已核准 #119 Corner Data Receiving switch lifecycle/readability 到目前最新 cleanup/2d-3d-sync；保留後續 UI 工作台改動，只帶 view lifecycle/post-commit visible refresh/dedicated viewport/readability，不改 manufacturing geometry、DXF authority 或 physical-part identity" \
  --changed-file fold_designer_bridge.py \
  --changed-file gui.py \
  --changed-file tests/test_issue119_corner_data_transition_ui.py \
  --changed-file tests/test_issue119_corner_data_knowledge_contract.py \
  --changed-file .agents/skills/engineering/截角資料入口收斂/SKILL.md \
  --changed-file "$AI_FILE" \
  --changed-file "$STATE_FILE" \
  --evidence /tmp/evidence.md

python -m py_compile fold_designer_bridge.py gui.py

python -m pytest -q \
  tests/test_issue119_corner_data_knowledge_contract.py \
  tests/process/test_issue128_invariant_manifest_contract.py \
  tests/test_ui_design_de_ai_skill_contract.py

python -m pytest -q \
  tests/test_dxf_acceptance.py \
  tests/test_receiving_door_dxf_roundtrip.py \
  tests/test_multipart_dxf_acceptance.py \
  tests/test_resolved_manufacturing_export.py \
  tests/test_resolved_manufacturing_geometry.py \
  tests/test_manufacturing_api_finished_face_contract.py \
  tests/test_issue41_persistence_parity.py \
  tests/test_issue45_dynamic_parts_2d_roundtrip.py \
  tests/test_phase6_project_controller.py \
  tests/test_phase6_project_file.py \
  tests/test_phase6_project_ownership.py \
  tests/test_phase6_project_session.py

timeout 600s xvfb-run -a python -m pytest -q -s \
  tests/test_issue119_corner_data_transition_ui.py \
  tests/test_issue94_corner_data_navigation_mode.py \
  tests/test_receiving_cabinet_type.py

mapfile -t ui_tests < <(find tests -maxdepth 1 -type f \( \
  -name 'test_issue123*.py' -o \
  -name 'test_issue124*.py' -o \
  -name 'test_issue125*.py' -o \
  -name 'test_issue126*.py' -o \
  -name 'test_issue127*.py' \
\) | sort)
test "${#ui_tests[@]}" -gt 0
printf '%s\n' "${ui_tests[@]}"
timeout 900s xvfb-run -a python -m pytest -q "${ui_tests[@]}"

sha256sum config.ini > /tmp/config.after
cmp /tmp/config.before /tmp/config.after
LC_ALL=C find 基準檔 -type f -print0 | sort -z | xargs -0 sha256sum > /tmp/baseline.after
diff -u /tmp/baseline.before /tmp/baseline.after
git diff --exit-code -- config.ini 基準檔
git diff --exit-code
test -z "$(git ls-files --others --exclude-standard)"

python - <<'PY'
from pathlib import Path
import os
p = Path('docs/superpowers/verification/2026-09-12-issue119-replay-state.md')
text = p.read_text(encoding='utf-8')
marker = '## Latest-production integration replay (40620c51)'
if marker not in text:
    text = text.rstrip() + f'''\n\n{marker}\n\n- Human `合` gate: RELEASED by user on 2026-09-12.\n- Fresh integration base: `40620c516ad099911ebd22c928237f81641759f2`.\n- Old accepted replay head: `7f894432ed7b4b4cdcd2160031c2f47e712cf436`.\n- Fresh integration branch: `fix/issue119-integration-latest-20260912-r2`.\n- Integration validation run: `{os.environ.get("GITHUB_RUN_ID", "unknown")}`.\n- Git auto-merged `fold_designer_bridge.py` and `gui.py`; the only merge conflict was append-vs-append in the AI pitfall library and was resolved by preserving both the #128 invariant-manifest rule and #119 Corner Data lifecycle/readability rule.\n- Original #119 final DXF/manufacturing/persistence and Xvfb matrices were rerun on the latest production baseline.\n- Current #123–#127 UI workstation regressions plus #128 durable invariant guard were rerun on the merged working tree.\n- `config.ini` and all protected files under `基準檔` remained byte/hash identical.\n- Validation remained judge-only; no geometry/manufacturing/DXF authority was derived from acceptance results.\n'''
    p.write_text(text + '\n', encoding='utf-8')
PY

git add "$STATE_FILE"
test -f .git/MERGE_HEAD
test -z "$(git -c core.quotePath=false diff --name-only --diff-filter=U)"
git diff --check --cached
git commit -m 'Merge #119 accepted Corner Data fix onto latest production'
git push origin HEAD:fix/issue119-integration-latest-20260912-r2
echo "ISSUE119_LATEST_INTEGRATION_GREEN head=$(git rev-parse HEAD) run=${GITHUB_RUN_ID:-unknown}"
