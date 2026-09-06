# T15 Per-Door Inner Door + Physical Panel Contract

## Authoritative state
- Receiving `inner_doors` list is the enable/presence Source of Truth.
- Each item owns one outer-door `cell_key` and deterministic `stable_id`.
- Tk `BooleanVar` values are UI adapters only and are rebuilt from authoritative state.

## Physical panel
- Checked/enabled outer door generates exactly one flat physical part: `inner_door:<inner_door_id>:panel`.
- Unchecked outer door generates no panel.
- Uncheck removes the part; re-enable of the same cell regenerates the same deterministic stable id.
- Panel finished size follows the same outer Door finished-face resolver, then Receiving inner-door insets are applied: left 50, right 50, top 50.
- Manufacturing owns the real CUTTING rectangle / material / unfolded blank; DesignerWorkspace stores only the derived profile projection.

## Existing capabilities that remain authoritative
- Existing inner-door top/left/right frame derivation remains intact.
- Single-door => 0 divider; multi-door topology alone derives dividers.
- Frame and panel derived parts share the `inner_door:` namespace and must be synchronized in one atomic `sync_derived_parts()` call so one class cannot delete the other.

## UI contract
- Receiving multi-door data row exposes one `內門` checkbox per Door cell.
- Checkbox operations change only their own cell state.

## Acceptance evidence
- Local full T15/guard gate: 38 PASS / 0 FAIL.
- Remote current-branch Xvfb targeted gate: 11 PASS / 0 FAIL.
- `config.ini` unchanged.
