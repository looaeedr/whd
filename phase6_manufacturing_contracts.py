"""Immutable Phase 2 manufacturing request contracts.

Task #355 intentionally introduces data contracts only.  The canonical
manufacturing resolver is not switched to these DTOs until later Phase 2 tasks.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum
import hashlib
import json
from numbers import Real
from typing import Any


@dataclass(frozen=True)
class FrozenMapping(Mapping[str, Any]):
    """Small immutable, hashable, order-canonical mapping."""

    _items: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        seen: set[str] = set()
        normalized: list[tuple[str, Any]] = []
        for key, value in tuple(self._items):
            skey = str(key)
            if skey in seen:
                raise ValueError(f"duplicate frozen mapping key after normalization: {skey!r}")
            seen.add(skey)
            normalized.append((skey, value))
        normalized.sort(key=lambda item: item[0])
        object.__setattr__(self, "_items", tuple(normalized))

    def __getitem__(self, key: str) -> Any:
        skey = str(key)
        for item_key, value in self._items:
            if item_key == skey:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def items(self):
        return self._items


def _freeze_dataclass(value: Any) -> FrozenMapping:
    payload = {
        "__dataclass_type__": f"{value.__class__.__module__}.{value.__class__.__qualname__}",
    }
    for field in fields(value):
        payload[field.name] = getattr(value, field.name)
    frozen = freeze_manufacturing_value(payload)
    assert isinstance(frozen, FrozenMapping)
    return frozen


def freeze_manufacturing_value(value: Any) -> Any:
    """Defensively freeze supported manufacturing data.

    Unsupported arbitrary objects and callbacks fail closed instead of leaking
    Tk/UI/runtime identity into the request graph.
    """
    if isinstance(value, FrozenMapping):
        return value
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, Enum):
        return freeze_manufacturing_value(value.value)
    if isinstance(value, Real):
        return round(float(value), 12)
    if callable(value):
        raise TypeError(f"callable is not valid manufacturing DTO data: {value!r}")
    if isinstance(value, Mapping):
        frozen_items = []
        seen: set[str] = set()
        for key, item in value.items():
            skey = str(key)
            if skey in seen:
                raise ValueError(f"duplicate mapping key after string normalization: {skey!r}")
            seen.add(skey)
            frozen_items.append((skey, freeze_manufacturing_value(item)))
        return FrozenMapping(tuple(frozen_items))
    if isinstance(value, (list, tuple)):
        return tuple(freeze_manufacturing_value(item) for item in value)
    if isinstance(value, (set, frozenset)):
        frozen = [freeze_manufacturing_value(item) for item in value]
        return tuple(sorted(frozen, key=repr))
    if is_dataclass(value):
        return _freeze_dataclass(value)

    module = str(getattr(value.__class__, "__module__", "") or "")
    if module == "tkinter" or module.startswith("tkinter."):
        raise TypeError(f"Tk object is not valid manufacturing DTO data: {value.__class__.__name__}")
    raise TypeError(
        "unsupported manufacturing DTO value "
        f"{value.__class__.__module__}.{value.__class__.__qualname__}"
    )


def _thaw_json_value(value: Any) -> Any:
    if isinstance(value, FrozenMapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    if value is None or isinstance(value, (bool, str, int, float)):
        return value
    if is_dataclass(value):
        return _thaw_json_value(_freeze_dataclass(value))
    raise TypeError(f"value is not canonical JSON-safe manufacturing data: {value!r}")


def canonical_manufacturing_json(value: Any) -> str:
    """Return deterministic canonical JSON for supported manufacturing data."""
    frozen = freeze_manufacturing_value(value)
    return json.dumps(
        _thaw_json_value(frozen),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def manufacturing_fingerprint(value: Any) -> str:
    payload = canonical_manufacturing_json(value).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _as_frozen_mapping(value: Any, *, field_name: str) -> FrozenMapping:
    frozen = freeze_manufacturing_value({} if value is None else value)
    if not isinstance(frozen, FrozenMapping):
        raise TypeError(f"{field_name} must be mapping-like")
    return frozen


def _as_frozen_sequence(value: Any) -> tuple[Any, ...]:
    frozen = freeze_manufacturing_value(() if value is None else value)
    if not isinstance(frozen, tuple):
        raise TypeError("manufacturing sequence field must be list/tuple/set-like")
    return frozen


@dataclass(frozen=True)
class ManufacturingPartInput:
    part_key: str
    scene_values: Any = None
    render_data: Any = None
    committed_render_data: Any = None
    part_spec: Any = None
    manufacturing_context: Any = None
    x_profile: Any = ()
    y_profile: Any = ()
    finished_dimensions: Any = None
    features: Any = ()
    face_features: Any = None
    box_body_structure: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "part_key", str(self.part_key or ""))
        if not self.part_key:
            raise ValueError("ManufacturingPartInput.part_key must be non-empty")
        object.__setattr__(
            self,
            "scene_values",
            _as_frozen_mapping(self.scene_values, field_name="scene_values"),
        )
        object.__setattr__(self, "x_profile", _as_frozen_sequence(self.x_profile))
        object.__setattr__(self, "y_profile", _as_frozen_sequence(self.y_profile))
        object.__setattr__(
            self,
            "finished_dimensions",
            freeze_manufacturing_value(self.finished_dimensions),
        )
        object.__setattr__(self, "features", _as_frozen_sequence(self.features))
        object.__setattr__(
            self,
            "face_features",
            freeze_manufacturing_value({} if self.face_features is None else self.face_features),
        )
        object.__setattr__(
            self,
            "box_body_structure",
            freeze_manufacturing_value({} if self.box_body_structure is None else self.box_body_structure),
        )

    def semantic_payload(self) -> FrozenMapping:
        return _as_frozen_mapping(
            {
                "part_key": self.part_key,
                "scene_values": self.scene_values,
                "x_profile": self.x_profile,
                "y_profile": self.y_profile,
                "finished_dimensions": self.finished_dimensions,
                "features": self.features,
                "face_features": self.face_features,
                "box_body_structure": self.box_body_structure,
            },
            field_name="part semantic payload",
        )


@dataclass(frozen=True)
class ManufacturingResolveRequest:
    source_revision: str = ""
    source_fingerprint: str = ""
    cache_key_fingerprint: str = ""
    input_snapshot: Any = None
    settings: Any = None
    box_dimensions: Any = None
    corner_state: Any = None
    endcap_fw: Any = None
    endcap_bottom_wrap: Any = None
    assembly_graph: Any = None
    canonical_part_keys: Any = ()
    parts: Any = ()
    operator_finished_dimensions: Any = None
    assembly_intent: str = ""
    allow_3d_fallback: bool = False
    relief_clearance: float = 0.0
    cabinet_model: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_revision", str(self.source_revision or ""))
        object.__setattr__(self, "source_fingerprint", str(self.source_fingerprint or ""))
        object.__setattr__(self, "cache_key_fingerprint", str(self.cache_key_fingerprint or ""))
        for name in (
            "input_snapshot",
            "settings",
            "box_dimensions",
            "corner_state",
            "endcap_fw",
            "endcap_bottom_wrap",
            "assembly_graph",
        ):
            object.__setattr__(
                self,
                name,
                _as_frozen_mapping(getattr(self, name), field_name=name),
            )

        part_keys: list[str] = []
        seen_part_keys: set[str] = set()
        for raw_key in tuple(self.canonical_part_keys or ()):
            key = str(raw_key or "")
            if key and key not in seen_part_keys:
                part_keys.append(key)
                seen_part_keys.add(key)
        object.__setattr__(self, "canonical_part_keys", tuple(part_keys))

        normalized_parts: list[ManufacturingPartInput] = []
        part_names: list[str] = []
        for item in tuple(self.parts or ()):
            if not isinstance(item, ManufacturingPartInput):
                raise TypeError("parts must contain ManufacturingPartInput values")
            if item.part_key in part_names:
                raise ValueError("duplicate ManufacturingPartInput.part_key")
            part_names.append(item.part_key)
            normalized_parts.append(item)
        object.__setattr__(self, "parts", tuple(normalized_parts))
        object.__setattr__(
            self,
            "operator_finished_dimensions",
            freeze_manufacturing_value(self.operator_finished_dimensions),
        )

        object.__setattr__(self, "assembly_intent", str(self.assembly_intent or ""))
        object.__setattr__(self, "allow_3d_fallback", bool(self.allow_3d_fallback))
        object.__setattr__(self, "relief_clearance", round(float(self.relief_clearance or 0.0), 12))
        object.__setattr__(self, "cabinet_model", str(self.cabinet_model or ""))

    def semantic_payload(self) -> FrozenMapping:
        """Manufacturing semantics only; revision/transport fingerprints excluded."""
        return _as_frozen_mapping(
            {
                "input_snapshot": self.input_snapshot,
                "settings": self.settings,
                "box_dimensions": self.box_dimensions,
                "corner_state": self.corner_state,
                "endcap_fw": self.endcap_fw,
                "endcap_bottom_wrap": self.endcap_bottom_wrap,
                "assembly_graph": self.assembly_graph,
                # Runtime assembly/render order is intentionally preserved on
                # the request object, while cache identity remains order-stable.
                "canonical_part_keys": tuple(sorted(self.canonical_part_keys)),
                "parts": tuple(
                    part.semantic_payload()
                    for part in sorted(self.parts, key=lambda item: item.part_key)
                ),
                "operator_finished_dimensions": self.operator_finished_dimensions,
                "assembly_intent": self.assembly_intent,
                "allow_3d_fallback": self.allow_3d_fallback,
                "relief_clearance": self.relief_clearance,
                "cabinet_model": self.cabinet_model,
            },
            field_name="request semantic payload",
        )


def manufacturing_request_fingerprint(request: ManufacturingResolveRequest) -> str:
    if not isinstance(request, ManufacturingResolveRequest):
        raise TypeError("request must be ManufacturingResolveRequest")
    return manufacturing_fingerprint(request.semantic_payload())


def thaw_manufacturing_value(value: Any) -> Any:
    """Return a detached mutable JSON-like representation for legacy adapters."""
    return _thaw_json_value(value)


@dataclass(frozen=True)
class FrozenObjectMapping(Mapping[str, Any]):
    """Immutable mapping envelope for opaque existing domain objects.

    Values are intentionally not serialized/frozen: existing geometry/solver
    result objects may contain Shapely/render objects.  The mapping container is
    immutable and copied at construction; ownership of the domain object itself
    remains with the existing frozen/domain contract.
    """

    _items: tuple[tuple[str, Any], ...] = ()

    def __post_init__(self) -> None:
        normalized: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for key, value in tuple(self._items):
            skey = str(key)
            if skey in seen:
                raise ValueError(f"duplicate object-mapping key: {skey!r}")
            seen.add(skey)
            normalized.append((skey, value))
        normalized.sort(key=lambda item: item[0])
        object.__setattr__(self, "_items", tuple(normalized))

    @classmethod
    def from_mapping(cls, value: Any) -> "FrozenObjectMapping":
        if isinstance(value, FrozenObjectMapping):
            return value
        if value is None:
            return cls()
        if not isinstance(value, Mapping):
            raise TypeError("opaque result field must be mapping-like")
        return cls(tuple((str(key), item) for key, item in value.items()))

    def __getitem__(self, key: str) -> Any:
        skey = str(key)
        for item_key, value in self._items:
            if item_key == skey:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)

    def items(self):
        return self._items


@dataclass(frozen=True)
class ManufacturingDiagnosticsResult:
    relief_errors: Any = None
    relief_solutions: Any = None
    joint_diagnostics: Any = ()
    rule_traces: Any = ()
    interference_probe_parts: Any = ()
    joint_marking_foundation: Any = None
    joint_marking_status: Any = None
    joint_marking_results: Any = ()
    joint_marking_export_summary: Any = ()
    warnings: Any = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "relief_errors",
            _as_frozen_mapping(self.relief_errors, field_name="relief_errors"),
        )
        object.__setattr__(
            self,
            "relief_solutions",
            FrozenObjectMapping.from_mapping(self.relief_solutions),
        )
        object.__setattr__(self, "joint_diagnostics", tuple(self.joint_diagnostics or ()))
        object.__setattr__(self, "rule_traces", tuple(self.rule_traces or ()))
        object.__setattr__(
            self,
            "interference_probe_parts",
            tuple(self.interference_probe_parts or ()),
        )
        object.__setattr__(
            self,
            "joint_marking_results",
            tuple(self.joint_marking_results or ()),
        )
        object.__setattr__(
            self,
            "joint_marking_export_summary",
            tuple(dict(item) for item in tuple(self.joint_marking_export_summary or ())),
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(str(item) for item in tuple(self.warnings or ())),
        )


@dataclass(frozen=True)
class ManufacturingMutationResult:
    snapshot_patch: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "snapshot_patch",
            _as_frozen_mapping(self.snapshot_patch, field_name="snapshot_patch"),
        )


@dataclass(frozen=True)
class ManufacturingEffects:
    publish_live_state: bool = False
    force_live_publish: bool = False
    reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "publish_live_state", bool(self.publish_live_state))
        object.__setattr__(self, "force_live_publish", bool(self.force_live_publish))
        object.__setattr__(self, "reason", str(self.reason or ""))


@dataclass(frozen=True)
class ManufacturingCacheReceipt:
    signature: str = ""
    hit: bool = False
    stored: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "signature", str(self.signature or ""))
        object.__setattr__(self, "hit", bool(self.hit))
        object.__setattr__(self, "stored", bool(self.stored))


@dataclass(frozen=True)
class ManufacturingResolveResult:
    geometry: Any
    diagnostics: ManufacturingDiagnosticsResult
    mutations: ManufacturingMutationResult
    effects: ManufacturingEffects
    cache: ManufacturingCacheReceipt

    def __post_init__(self) -> None:
        if not isinstance(self.diagnostics, ManufacturingDiagnosticsResult):
            raise TypeError("diagnostics must be ManufacturingDiagnosticsResult")
        if not isinstance(self.mutations, ManufacturingMutationResult):
            raise TypeError("mutations must be ManufacturingMutationResult")
        if not isinstance(self.effects, ManufacturingEffects):
            raise TypeError("effects must be ManufacturingEffects")
        if not isinstance(self.cache, ManufacturingCacheReceipt):
            raise TypeError("cache must be ManufacturingCacheReceipt")


__all__ = [
    "FrozenMapping",
    "FrozenObjectMapping",
    "ManufacturingPartInput",
    "ManufacturingResolveRequest",
    "ManufacturingDiagnosticsResult",
    "ManufacturingMutationResult",
    "ManufacturingEffects",
    "ManufacturingCacheReceipt",
    "ManufacturingResolveResult",
    "canonical_manufacturing_json",
    "freeze_manufacturing_value",
    "manufacturing_fingerprint",
    "manufacturing_request_fingerprint",
    "thaw_manufacturing_value",
]
