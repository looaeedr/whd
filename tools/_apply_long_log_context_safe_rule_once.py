# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import textwrap
from pathlib import Path

MARKER = "LONG_LOG_CONTEXT_SAFE_EXECUTION_V1"


def dedent(text: str) -> str:
    return textwrap.dedent(text).strip() + "\n"


def replace_once(text: str, old: str, new: str, *, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"missing anchor for {label}: {old!r}")
    return text.replace(old, new, 1)


def main() -> None:
    skill_path = Path(".agents/skills/engineering/long-log-context-safe-execution/SKILL.md")
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(
        dedent(
            """
            ---
            name: long-log-context-safe-execution
            description: Use when commands, tests, remote CI, pytest, Xvfb, Combined Acceptance, or other long-running jobs can produce logs large enough to overflow or repeatedly consume the execution/chat context.
            ---

            # Long-Log Handling / Context-Safe Execution

            ## LONG_LOG_CONTEXT_SAFE_EXECUTION_V1

            超長 Log 的完整內容屬於**持久化證據**，不是日常監控 payload。核心原則：**raw log 落檔／artifact；context 只看結構化狀態、固定上限 tail、錯誤切片與 cursor 後的新內容。**

            ## 何時強制使用

            - pytest / Xvfb / full-suite / Combined Acceptance 等輸出可能達數百到數千行。
            - GitHub Actions / remote CI 長時間執行，需要多次 polling。
            - 本機 command/process 持續輸出，而下一輪只需要新增輸出。
            - Runtime、聊天或執行視窗可能被平台切斷，需要 checkpoint 續接。

            ## 強制規則

            1. **禁止把完整超長 Log 灌進執行／聊天 context。** 完整 raw log 應寫入檔案、CI artifact、provider job log 或其他 durable storage；畫面與 context 只讀有限片段。
            2. **正常執行只讀摘要 + bounded tail。** 每輪優先讀 process/run/job/step 狀態、iteration、PASS/FAIL/score、elapsed，以及最後固定上限 N 行。N 必須有上限，不能隨 log 成長；預設可從 80 行以下開始。
            3. **FAIL 先定位、再切片。** 先搜尋 `FAILED`、`ERROR`、`Traceback`、`AssertionError`、exit code 或 provider failed-step annotation，只擷取命中點前後有限區段；不足才按 chunk 向外擴。
            4. **分段反讀必須保留 offset/cursor。** 對 line/byte range、resource cursor、`next_read`、artifact offset 等記錄 `last_read_offset`；下一輪從 checkpoint 後續讀，禁止因 context 截斷就從第 1 行重讀。
            5. **遠端 QA 優先結構化狀態。** polling 用 run → jobs → steps；失敗時優先 failed-job/failed-step log、搜尋或 bounded slice。若環境真的有 GitHub CLI，可用 `gh run view <run> --log-failed`；沒有 CLI 就用 connector/API 等價能力，不得假裝工具存在。
            6. **provider 只能整包下載時，先落檔再搜尋。** 不得把整份下載內容直接回傳聊天；先保存 raw file，再以 grep/search/find/offset 取需要的片段。
            7. **執行視窗被切斷 ≠ 工作失敗。** 恢復時先反查 durable `run_id/process_id + branch + HEAD + checkpoint + artifact/raw-log location + last_read_offset + last known state`，再續同一工作；禁止只因聊天中斷就重新跑整套測試。
            8. **terminal 後才做完整 evidence 收斂。** 終態收 pass/fail counts、failed nodeids、invariants、head SHA、cleanup/drift evidence；完整 raw log 可作證據來源，但仍不必整份搬入 context。

            ## Checkpoint 最小欄位

            長流程至少保存：`branch`、`head_sha`、`run_id/process_id`、`state`、`active_step`、`pass/fail/score`、`raw_log_path/artifact`、`last_read_offset/cursor`、`last_tail_range`、`known_failures`、`next_exact_action`。

            ## Context-safe 讀取策略

            | 狀態 | 動作 |
            |---|---|
            | queued / running | structured status + bounded tail/new chunk；更新 cursor；依 owning cadence 回報 |
            | failed | 搜 failure marker → bounded error slice → 必要時向外擴；raw log 留 durable storage |
            | terminal success | 收 counts / invariants / HEAD / cleanup evidence；不重播整份 log |
            | Runtime cut | 讀 checkpoint → 驗 branch/HEAD/run → 從 cursor 續讀；不重 trigger |

            ## 禁止事項

            - 每次 polling 都重新 fetch / paste 整份 job log。
            - 因 tool response 被截斷就從頭再抓一次超長 log。
            - 用「log 太長看不到」當成重跑 full-suite 的理由。
            - non-terminal 長流程等全部跑完才第一次回報；應依 owning monitoring/long-run cadence 回報狀態、iteration、score 或 bounded tail。
            - 把 raw log 當成 production/domain authority；log 只提供 validation/evidence。

            `monitoring-remote-qa` 擁有 remote run 的 active polling state machine；本 Skill 擁有**所有長輸出的 context-safe 讀取與續接策略**。兩者不得建立第二套互相衝突的 state machine。
            """
        ),
        encoding="utf-8",
    )

    pitfall_path = Path("個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md")
    pitfall_path.parent.mkdir(parents=True, exist_ok=True)
    pitfall_path.write_text(
        dedent(
            """
            # 超長 Log / Context-Safe Execution 踩坑

            ## LONG_LOG_CONTEXT_SAFE_EXECUTION_V1

            ### 事故模式

            長 pytest / Xvfb / Combined Acceptance 或 GitHub Actions 產生數千行輸出時，若每輪監控都把完整 Log 重新抓進執行／聊天視窗，會快速耗盡 context、造成 tool response 截斷，甚至讓 Runtime 被切斷。切斷後若又從頭重讀或重跑 full-suite，就形成「越查越長、越長越重跑」循環。

            ### 根因

            - 把 raw log 當成監控畫面，而不是 durable evidence source。
            - 沒有 tail 上限與 offset/cursor，導致每次都從頭讀。
            - FAIL 後不先定位 failure marker，直接下載／貼整包 log。
            - 把聊天 Runtime 誤當 remote process lifecycle owner；視窗一斷就重 trigger。

            ### 永久規則

            - 完整 raw log 落檔、artifact 或 provider job log；context 禁止整包灌入。
            - running 期間只讀 structured state、進度、PASS/FAIL/score 與 bounded tail；固定上限，不因 log 變長而擴張。
            - FAIL 先找 `FAILED/ERROR/Traceback/AssertionError` 或 failed step，再讀前後有限區段；不足才分段向外擴。
            - 每次 chunk read 保存 line/byte offset 或 cursor；context 被裁切也從 checkpoint 續讀，不從頭重讀。
            - GitHub Actions polling 優先 run/jobs/steps；有 `gh` 才用 `gh run view ... --log-failed`，沒有就用 connector/API 的 failed-job/bounded-search 等價路徑。
            - provider 只能整包下載時，先保存 raw file，再在檔案上 search/tail；禁止把整包回傳聊天。
            - 執行視窗被切斷不等於工作失敗。恢復順序：反查 run/process → branch/HEAD → durable evidence/artifact → cursor → latest state → next exact action；禁止先重跑。
            - terminal 後才收斂完整 evidence；raw log 是證據來源，不是每次監控都要搬進 context 的內容。

            Canonical execution rule：`.agents/skills/engineering/long-log-context-safe-execution/SKILL.md`。Remote QA state machine 仍由 `.agents/skills/engineering/monitoring-remote-qa/SKILL.md` 擁有。
            """
        ),
        encoding="utf-8",
    )

    monitoring_path = Path(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")
    monitoring = monitoring_path.read_text(encoding="utf-8")
    if MARKER not in monitoring:
        anchor = "# Monitoring Remote QA\n\n"
        bridge = dedent(
            """
            ## LONG_LOG_CONTEXT_SAFE_EXECUTION_V1 bridge

            Remote QA 的 polling 狀態機仍由本 Skill 擁有；**長 Log 的讀取方式一律委派** `.agents/skills/engineering/long-log-context-safe-execution/SKILL.md`。正常 poll 只讀 run/jobs/steps + bounded tail/new chunk；完整 raw log 落檔／artifact。FAIL 先定位 failed step/error marker 再讀有限上下文，禁止每輪把整份 job log 灌進 context。

            """
        )
        monitoring = replace_once(monitoring, anchor, anchor + bridge, label="monitor bridge")
        monitoring = replace_once(
            monitoring,
            "When a job or step fails, fetch its log immediately.",
            "When a job or step fails, immediately locate the failed step/error marker and retrieve only a bounded failure slice; if the provider exposes only a full download, persist it first and search/chunk it outside the chat context.",
            label="active polling failure-log rule",
        )
        monitoring = replace_once(
            monitoring,
            "3. If a job fails, fetch that job log immediately. Classify the failure as production/test failure vs harness/runner/setup failure using the project debugging/timeout rules.",
            "3. If a job fails, locate the failed step/error first and read a bounded slice under `LONG_LOG_CONTEXT_SAFE_EXECUTION_V1`; do not repeatedly fetch/paste the whole log. Classify the failure as production/test failure vs harness/runner/setup failure using the project debugging/timeout rules.",
            label="required loop failure-log rule",
        )
        mistake = "- Polling only the run status and never checking which job/step failed.\n"
        monitoring = replace_once(
            monitoring,
            mistake,
            mistake + "- Re-fetching or pasting the complete long job log on every poll instead of using bounded failed slices / tail + cursor.\n",
            label="monitor common mistake",
        )
        monitoring_path.write_text(monitoring, encoding="utf-8")

    agents_path = Path("AGENTS.md")
    agents = agents_path.read_text(encoding="utf-8")
    if MARKER not in agents:
        anchor = "### 0.0.3 成品板件驗收硬閘門：Focused GREEN 不能直接合併\n"
        section = dedent(
            """
            ### 0.0.2 超長 Log / Context-Safe Execution 硬閘門

            <!-- LONG_LOG_CONTEXT_SAFE_EXECUTION_V1 -->
            pytest、Xvfb、Combined Acceptance、remote CI 或其他長流程只要可能產生大量輸出，就必須讀並遵守：

            `.agents/skills/engineering/long-log-context-safe-execution/SKILL.md`

            硬規則：完整 raw log 落檔／artifact，不得整包灌入執行或聊天 context；running 期間只讀 structured status、bounded tail/new chunk；FAIL 先定位 failure marker 再擷取有限上下文；分段讀取必須保存 offset/cursor；Runtime/聊天視窗被切斷後先反查 run/process + branch + HEAD + checkpoint + artifact + cursor，從同一工作續接，禁止因視窗中斷就重跑 full-suite。Remote QA 的 30 秒 active polling 仍由 `monitoring-remote-qa` 擁有，本 gate 不建立第二套 polling state machine。

            """
        )
        agents = replace_once(agents, anchor, section + anchor, label="AGENTS long-log gate")
        agents_path.write_text(agents, encoding="utf-8")

    readme_path = Path(".agents/skills/engineering/README.md")
    readme = readme_path.read_text(encoding="utf-8")
    new_bullet = "- **[long-log-context-safe-execution](./long-log-context-safe-execution/SKILL.md)**: 超長 pytest/Xvfb/remote CI 輸出的落檔、bounded tail、failure slice、cursor 與 Runtime-cut 續接規則。\n"
    if new_bullet not in readme:
        anchor = "- **[monitoring-remote-qa](./monitoring-remote-qa/SKILL.md)**\n"
        readme = replace_once(readme, anchor, anchor + new_bullet, label="engineering README navigation")
        readme_path.write_text(readme, encoding="utf-8")

    global_pitfall_path = Path("個人AI檔案庫/第二層_專案與SOP/06_踩坑記錄與防錯經驗庫.md")
    global_pitfall = global_pitfall_path.read_text(encoding="utf-8")
    if MARKER not in global_pitfall:
        anchor = "# ⚠️ 06. 踩坑記錄與防錯經驗庫 (Bad Patterns & Lessons Learned)\n"
        pointer = dedent(
            """

            ## 執行／監控踩坑索引 — LONG_LOG_CONTEXT_SAFE_EXECUTION_V1

            超長 pytest / Xvfb / Combined Acceptance / GitHub Actions Log 不得反覆整包灌入 context；canonical 規則見 `.agents/skills/engineering/long-log-context-safe-execution/SKILL.md`，事故與復原細節見 `個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md`。

            """
        )
        global_pitfall = replace_once(global_pitfall, anchor, anchor + pointer, label="global pitfall index")
        global_pitfall_path.write_text(global_pitfall, encoding="utf-8")

    registry_path = Path(".agents/skills/skill_registry.json")
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    routes = registry["routes"]
    route_id = "long-log-context-safe-execution"
    if not any(route.get("id") == route_id for route in routes):
        new_route = {
            "id": route_id,
            "keywords": [
                "超長 Log",
                "長輸出",
                "Long-Log",
                "long log",
                "context-safe execution",
                "tail output",
                "tail log",
                "log-failed",
                "offset cursor",
                "log 太長",
                "Xvfb full-suite",
                "Combined Acceptance log",
            ],
            "file_globs": [],
            "required_skills": ["long-log-context-safe-execution"],
            "required_references": ["個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md"],
        }
        insert_at = next(i for i, route in enumerate(routes) if route.get("id") == "remote-qa-monitoring")
        routes.insert(insert_at, new_route)

    remote = next(route for route in routes if route.get("id") == "remote-qa-monitoring")
    for skill_name in ("monitoring-remote-qa", "long-log-context-safe-execution"):
        if skill_name not in remote["required_skills"]:
            remote["required_skills"].append(skill_name)
    pitfall_ref = "個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md"
    if pitfall_ref not in remote["required_references"]:
        remote["required_references"].append(pitfall_ref)
    registry_path.write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    test_path = Path("tests/process/test_long_log_context_safe_execution_contract.py")
    test_path.write_text(
        dedent(
            """
            from pathlib import Path
            import json

            MARKER = "LONG_LOG_CONTEXT_SAFE_EXECUTION_V1"
            SKILL = Path(".agents/skills/engineering/long-log-context-safe-execution/SKILL.md")
            MONITOR = Path(".agents/skills/engineering/monitoring-remote-qa/SKILL.md")
            AGENTS = Path("AGENTS.md")
            PITFALL = Path("個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md")
            REGISTRY = Path(".agents/skills/skill_registry.json")


            def _read(path: Path) -> str:
                return path.read_text(encoding="utf-8")


            def test_canonical_long_log_skill_locks_context_safe_behavior():
                text = _read(SKILL)
                assert MARKER in text
                assert "禁止把完整超長 Log" in text
                assert "bounded tail" in text
                assert "offset/cursor" in text
                assert "FAIL 先定位" in text
                assert "執行視窗被切斷 ≠ 工作失敗" in text
                assert "terminal 後才做完整 evidence 收斂" in text


            def test_remote_qa_bridges_to_long_log_authority_without_second_polling_machine():
                text = _read(MONITOR)
                assert MARKER in text
                assert "long-log-context-safe-execution/SKILL.md" in text
                assert "bounded failure slice" in text
                assert "whole log" in text
                assert "REMOTE_QA_ACTIVE_LOCK" in text


            def test_agents_and_ai_pitfall_make_rule_durable():
                agents = _read(AGENTS)
                pitfall = _read(PITFALL)
                assert MARKER in agents
                assert "long-log-context-safe-execution/SKILL.md" in agents
                assert MARKER in pitfall
                assert "offset/cursor" in pitfall
                assert "禁止先重跑" in pitfall


            def test_preflight_registry_routes_long_logs_and_remote_qa_to_context_safe_skill():
                data = json.loads(_read(REGISTRY))
                routes = {route["id"]: route for route in data["routes"]}
                long_log = routes["long-log-context-safe-execution"]
                assert "long-log-context-safe-execution" in long_log["required_skills"]
                assert "個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md" in long_log["required_references"]
                remote = routes["remote-qa-monitoring"]
                assert "monitoring-remote-qa" in remote["required_skills"]
                assert "long-log-context-safe-execution" in remote["required_skills"]
                assert "個人AI檔案庫/踩坑庫/long_log_context_safe_execution.md" in remote["required_references"]
            """
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
