# -*- coding: utf-8 -*-
"""Typed, UI-independent Phase 4 Final Scene contracts."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class AssemblyScenePart:
    part_key: str
    render_data: object
    x_profile: tuple[Mapping[str, object], ...]
    y_profile: tuple[Mapping[str, object], ...]
    placement: str = "offset"
    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass(frozen=True)
class AssemblySceneRenderData:
    assembly_parts: tuple[AssemblyScenePart, ...]
    visible_part_keys: tuple[str, ...] | None = None
    visible_box_body_piece_keys: tuple[str, ...] | None = None
    warnings: tuple[object, ...] = ()
    show_interference: bool = False
    ignore_fixed_corner_relief: bool = False
    interference_probe_parts: tuple[AssemblyScenePart, ...] = ()
    joint_diagnostics: tuple[object, ...] = ()
    selected_joint_id: str | None = None
    preserve_endcap_core_origin: bool = False


@dataclass(frozen=True)
class FinalSceneViewRequest:
    render_data: object
    x_profile: tuple[Mapping[str, object], ...]
    y_profile: tuple[Mapping[str, object], ...]
    part_key: str
    alpha_bend: float = 0.85
    finished_dimensions: tuple[float, ...] | None = None
    thickness: float = 2.0
    corner_dimension_text: str | None = None
    unfolded_blank_text: str | None = None


@dataclass(frozen=True)
class FinalSceneRuntimeState:
    last_cutting_mesh: tuple[object, ...] = ()
    last_cutting_material: object | None = None
    cutting_mesh_error: str | None = None
    zoom_scale: float = 1.0
    view_initialized: bool = False
    base_renderer_render: object | None = None
    scroll_cid: object | None = None
    last_interference_diagnostic: object | None = None


@dataclass(frozen=True)
class FinalSceneEffects:
    after_render: bool = False
    mirror_runtime_state: bool = False
    metadata: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class FinalSceneRenderResult:
    request: FinalSceneViewRequest | None = None
    triangles: tuple[object, ...] = ()
    runtime_state: FinalSceneRuntimeState = field(
        default_factory=FinalSceneRuntimeState
    )
    effects: FinalSceneEffects = field(default_factory=FinalSceneEffects)


@dataclass(frozen=True)
class FinalSceneDependencies:
    """Explicit named Final Scene ports.

    Required callables fail closed at construction. Optional compatibility/view
    hooks remain explicit fields until later Phase 4 tasks remove them.
    """

    number_text: Callable[[object], str] | None = None
    is_physical_piece_key: Callable[[str], bool] | None = None
    physical_piece_render_data: Callable[[str], object] | None = None
    user_joint_parts: Callable[[], object] | None = None
    resolve_geometry: Callable[[], object] | None = None
    scene_payload_for_part: Callable[[str], object] | None = None
    publish_live_state: Callable[..., object] | None = None
    corner_dimension_text: Callable[[object], str] | None = None
    formed_size_text: Callable[..., str] | None = None
    blank_text: Callable[..., str] | None = None
    refresh_box_body_piece_info: Callable[[object], object] | None = None
    operator_dimensions: Callable[..., object] | None = None
    cabinet_family: Callable[[], str] | None = None
    assembly_blank_text: Callable[[object], str] | None = None
    active_mesh_profiles: Callable[[object], object] | None = None
    assembly_render_data_cls: type = AssemblySceneRenderData
    assembly_part_cls: type = AssemblyScenePart
    final_render_provider: Callable[[], object] | None = None
    assembly_render_provider: Callable[[], object] | None = None
    request_provider: Callable[[], FinalSceneViewRequest | None] | None = None
    after_render: Callable[[], object] | None = None

    # T6 explicit application/view ports. These replace the generic app-owner
    # reference that the adapter used to retain.
    active_part: Callable[[], str] | None = None
    scene_query: Callable[[str, object], object] | None = None
    input_snapshot: Callable[[], Mapping[str, object]] | None = None
    settings_values: Callable[[], Mapping[str, object]] | None = None
    alpha_bend: Callable[[], float] | None = None
    display_mode: Callable[[], str] | None = None
    assembly_corner_text_sink: Callable[[Mapping[str, str]], object] | None = None
    assembly_part_text_sink: Callable[[str, str, str], object] | None = None
    assembly_visibility: Callable[[tuple[AssemblyScenePart, ...]], object] | None = None
    interference_probe_parts: Callable[[], object] | None = None
    show_interference: Callable[[], bool] | None = None
    render_committed: Callable[[], object] | None = None
    set_preview_enabled: Callable[[bool], object] | None = None
    refresh_preview: Callable[[], object] | None = None

    def __post_init__(self) -> None:
        required = (
            "is_physical_piece_key",
            "physical_piece_render_data",
            "user_joint_parts",
            "resolve_geometry",
            "scene_payload_for_part",
            "publish_live_state",
            "corner_dimension_text",
            "formed_size_text",
            "blank_text",
            "operator_dimensions",
            "cabinet_family",
            "assembly_blank_text",
            "active_mesh_profiles",
            "active_part",
            "scene_query",
            "input_snapshot",
            "settings_values",
            "alpha_bend",
            "display_mode",
            "assembly_corner_text_sink",
            "assembly_part_text_sink",
            "assembly_visibility",
            "interference_probe_parts",
            "show_interference",
            "render_committed",
            "set_preview_enabled",
            "refresh_preview",
        )
        missing = [
            name for name in required
            if not callable(getattr(self, name))
        ]
        if missing:
            raise ValueError(
                "Final Scene required dependencies are not connected: "
                + ", ".join(missing)
            )
        for name in (
            "number_text",
            "refresh_box_body_piece_info",
            "final_render_provider",
            "assembly_render_provider",
            "request_provider",
            "after_render",
        ):
            value = getattr(self, name)
            if value is not None and not callable(value):
                raise TypeError(
                    f"Final Scene dependency {name} must be callable or None"
                )
        if not isinstance(self.assembly_render_data_cls, type):
            raise TypeError("assembly_render_data_cls must be a type")
        if not isinstance(self.assembly_part_cls, type):
            raise TypeError("assembly_part_cls must be a type")


__all__ = [
    "AssemblyScenePart",
    "AssemblySceneRenderData",
    "FinalSceneDependencies",
    "FinalSceneEffects",
    "FinalSceneRenderResult",
    "FinalSceneRuntimeState",
    "FinalSceneViewRequest",
]
