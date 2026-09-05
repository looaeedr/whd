# GUI Interaction Geometry Design

**Goal:** Remove the remaining manufacturing/feature coordinate derivation from `gui.py` while preserving the current Vault-type GUI behavior.

## Scope

1. Door indicator hit-test, drag bounds, and X/Y positioning dimensions.
2. End-cap hole-editor selection hit-test.
3. Base-plate four mounting holes shared by GUI and DXF.
4. Canvas continues to transform/render only; it must not own manufacturing coordinates.

## Architecture

`sheetmetal_features.py` becomes the single source for feature placement and interaction geometry.

```text
Feature/Part parameters
  -> resolved feature/layout geometry
     -> GUI Canvas transform/render/hit-test
     -> DXF serialization
```

### Door indicator

Add a resolved layout object containing:

- resolved holes/marks,
- interaction bounds,
- left-most lamp center,
- top-most lamp center,
- group/base center,
- clamped offset helpers,
- positioning-dimension geometry.

The legacy constants such as `191`, `171`, `133.5`, `17.25`, active envelope width/height, etc. may remain inside the Vault door-indicator feature policy, but must disappear from `gui.py`.

### End-cap hole editor

Add world-space feature resolution/hit-test helpers. GUI converts mouse pixels with `CanvasTransform.canvas_to_world()` and asks the feature layer which feature was hit. Hit-testing must understand circle/rectangle extents instead of comparing pixel distance only to feature centers.

### Base plate mounting holes

Add one resolver for the four diameter-10 holes using current manufacturing rule:

```text
center offset from each bend line = 15 mm
radius = 5 mm
layer = CUTTING
```

Both GUI preview and `ae.py` must consume the same resolved circles.

## Compatibility

- Preserve current Vault indicator pattern and drag limits.
- Preserve current positioning dimension meaning.
- Preserve current end-cap hole list/storage format.
- Preserve current base-plate hole positions and diameter.
- No Tkinter/ezdxf imports in `sheetmetal_features.py`.

## Tests

- Door indicator layout reproduces existing one-group and multi-group geometry.
- Interaction hit-test works inside/outside the envelope.
- Drag offset clamping preserves finished-face bounds.
- X/Y dimension values and reverse-setting offsets round-trip.
- Circle/rectangle feature hit-tests use world coordinates.
- Base plate hole resolver produces the exact four current centers.
- Source audit: door interaction formulas and base-plate hole formulas disappear from `gui.py`; base-plate hole formula disappears from `ae.py`.
