# T13 Receiving Base Plate 55 Contract

## Canonical contract

```text
Receiving family preset
    -> base_plate_shrink Top/Bottom/Left/Right = 55 mm
    -> resolve nominal finished face
    -> build base-plate folds
    -> apply local seam relief only where a real box-body seam intersects the finished face
    -> 2D / 3D / DXF / Save-Reload consume the same result
```

### Dimension spaces

For the current Receiving default `W=800, H=1600, bend=15`:

- finished face width = `800 - 55 - 55 = 690`
- finished face height = `1600 - 55 - 55 = 1490`
- unfolded structural blank width = `690 + 15 + 15 = 720`
- unfolded structural blank height = `1490 + 15 + 15 = 1520`

The 55 mm values are **nominal family shrink**, not seam-relief allowance.

## Local seam relief

`apply_base_plate_structure_reliefs()` is a second-stage manufacturing operation.

- it receives the already-resolved base plate;
- it uses `finished_left=shrink_left` and `finished_right=W-shrink_right` to decide whether a seam intersects the finished face;
- only a real intersection gets the configured local relief (current canonical total length 20 mm and 0.5T retained meat);
- a seam outside the 55-mm finished-face boundary does nothing;
- relief may alter local CUTTING/BEND segments but **must not rewrite shrink values or nominal finished dimensions**.

## Forbidden behavior

- Receiving-specific `st/sb/sl/sr = 0` suppression in Manufacturing.
- Main 2D or 3D part-dimension special cases that use `base_w=W, base_h=H` solely because model=Receiving.
- Treating the 55-mm family shrink and local 20-mm seam relief as one global shortening operation.
- Changing Vault base-plate behavior while fixing Receiving.
- Resetting 55 during resolve/rebuild/project reload.

## Persistence / round-trip

A fresh Receiving project stores all four shrink values as 55. Save→Reload→3D must restore the same 55 values and the same 690×1490 finished base-plate dimensions.

## Regression IDs

- R01: Receiving fresh default = 55/55/55/55.
- R02: local seam relief runs after the nominal 55 shrink and never converts it to zero.
