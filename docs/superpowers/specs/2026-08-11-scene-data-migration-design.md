# Scene Data Migration Design

## Goal
Eliminate the legacy `geom = {'polylines': [], 'lines': [], 'circles': [], 'params': ...}` contract. Stretched baseline mappers and Indicator Box generation must produce `DrawingScene` primitives directly.

## Contract
Add a pure `SceneData` container in `sheetmetal_drawing.py`:

```python
@dataclass
class SceneData:
    scene: DrawingScene
    params: dict[str, object] = field(default_factory=dict)
    metadata: dict[str, object] = field(default_factory=dict)
```

`scene` contains all drawable output. `params` contains dimensions/fold values required by callers. `metadata` contains non-drawing state such as `door_indicator_layout`.

## Migration
- `get_stretched_end_cap_data()` returns `SceneData`.
- `get_stretched_box_body_data()` returns `SceneData`.
- `get_stretched_door_data()` returns `SceneData`.
- `get_indicator_box_data()` returns `SceneData`.
- Callers consume `.scene`, `.params`, `.metadata`.
- Baseline entity mapping appends `PolylinePrimitive`, `LinePrimitive`, `CirclePrimitive` directly.
- Remove `legacy_geom_to_primitives()` after all producers and consumers migrate.

## Constraints
- No geometry/formula change in this phase.
- Preserve primitive order and layers.
- MARKING color semantics remain serializer-owned/primitive-owned as currently defined.
- Baseline mapping logic remains unchanged except for its output data structure.
- `sheetmetal_drawing.py` remains independent of ezdxf/tkinter/shapely.
