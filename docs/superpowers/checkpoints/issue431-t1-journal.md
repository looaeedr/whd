# Issue #431 / T1 — Shared-content host & mutually-exclusive mode controller

## Authority
- Parent: #429
- Predecessor: #430 CLOSED/completed
- T1 base / #430 closing SHA: `95ab91c900e9a531ce0fec25a698123116392cc2`
- Work branch: `refactor/issue431-t1-shared-content-host-20260920`

## Knowledge Preflight
- RUN `35495987364` / JOB `106038887410`
- HEAD `22bb3a35b80858c121ff0e38eabe31c0c5039b30`
- result: SUCCESS / `KNOWLEDGE_PREFLIGHT_RC=0`

## Intended RED
- RUN `35496092853`
- JOB `106039190087`
- RED HEAD `7d4c569c5936924120ec0b520f7afd61bbd07fb2`
- artifact `issue431-t1` / ID `10600184890`
- artifact SHA256 `71517025f6d79d8734d880555aaf50d12ad3587b1b386552b780637099e1811d`

Exact result:
```text
5 PASS
3 intended FAIL
0 SKIP
```

Exact REDs:
1. inherited #430: three direct-left content hosts instead of one;
2. #431: dedicated shared-content host missing;
3. #431: shared-content mount controller missing.

## Minimal GREEN change
Only `fold_designer_bridge.py` production ownership is changed:

- add one `shared_content_host` directly under `self.left`;
- construct existing Assembly panel under that host;
- construct existing Fold editor under that host;
- lazily construct existing Corner Data panel under that host;
- centralize content `pack / pack_forget` in `_phase6_mount_shared_content()`;
- callers still own the existing `_phase6_3d_display_mode` transitions;
- `designer_workspace.active_part`, visibility vars, Corner Data adapter state, geometry, persistence and callbacks remain unchanged.

No internal Assembly/part/Corner Data content behavior is rewritten.

## GREEN pending
Required focused gates:
```text
SHARED_CONTENT_HOST_COUNT=1
ACTIVE_SHARED_CONTENT_MODE_COUNT=1
SEPARATE_ASSEMBLY_REGION=0
SEPARATE_CORNER_DATA_REGION=0
MODE_SWITCH_CREATES_STATE_AUTHORITY=0
```

## State
```text
STATE=GREEN_PENDING
NEXT_ACTION=Run the same 8-node behavior matrix on the production-change HEAD and require 8 PASS / 0 FAIL / 0 SKIP.
```
