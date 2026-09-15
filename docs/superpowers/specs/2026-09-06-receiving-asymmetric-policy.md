# T12 Receiving Asymmetric Policy

## Canonical family rule

Receiving / 受電箱 is a formally **asymmetric cabinet family**.

Generic BoxBody mirrored editing is therefore not a user preference for this
family.  The capability is false at the family-policy layer:

```text
cabinet family
    -> box_body_symmetry_allowed()
       Receiving = false
       Vault = true
    -> authoritative 3D state
    -> Fold Editor controls
    -> mirror / delete behavior
```

## Required behavior

- Receiving effective `state.symmetric` is always `False`.
- Receiving must not display any effective `對稱折彎` control in the 3D
  Designer, including both the original top-level control and the Phase6 Fold
  Editor symmetry bar.
- Direct/programmatic attempts to set `v_sy=True` must be rejected
  fail-closed.
- Mirror-on-edit and mirror-on-remove logic must independently check the family
  capability so stale/direct state mutation cannot make symmetry effective.
- Loading a Receiving project must normalize symmetry to false before rendering.
  The original Designer default `symmetric=True` must never revive Receiving
  symmetry.
- Vault keeps its generic symmetry control and can toggle false/true normally.
- Vault -> Receiving immediately forces false and hides the controls again.
- `RECEIVING` is a supported alias of the canonical `受電箱` family.

## Persistence boundary

No new project schema field is required for Receiving symmetry.  Family policy
is authoritative: on every Receiving load the effective value is false.
Project Save/Reload must therefore never recreate symmetry through the original
AppState default.

## Forbidden

- UI-only `pack_forget` while leaving effective `state.symmetric=True`.
- Allowing direct `state.symmetric=True` to drive mirror/remove behavior in Receiving.
- Disabling Vault symmetry while fixing Receiving.
- Duplicating Receiving checks as scattered string literals instead of the
  cabinet-family capability.
