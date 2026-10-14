# WHD 尺寸硬契約（CURRENT：個人AI檔案庫/第二層_專案與SOP/07_Phase6尺寸語意與標準截角母規則.md）：
# 3D 操作輸入為唯一資料來源，輸入的是折後包外尺寸及折彎方向；不可用下游組合體回寫輸入。
# 同一拓樸／板厚 T：料長 = 包外 − 實際相鄰 BEND 數(0/1/2)*T；包外 = 料長 + 同一折彎數*T。
# 展開 BEND = 料長前綴和；由展開邊界與 BEND 差分得料長，再按拓樸/T 可反算包外，正反算須一致。
# 單板3D、組合3D、2D及製造/DXF都由這份輸入推導；角度正負只定折彎方向，WRAP/OVERLAY 是裝配語意.

"""Quantity demand is a projection of the resolved physical inventory."""
from dataclasses import dataclass
from types import SimpleNamespace
from .manufacturing_export import resolved_physical_render_parts


@dataclass(frozen=True)
class ResolvedQuantityVersion:
    version_id: str
    piece_count: int
    geometry: object


@dataclass(frozen=True)
class PhysicalPartDemand:
    version_id: str
    source_part_id: str
    physical_id: str
    piece_count: int
    per_box_count: int
    render_data: object

    @property
    def quantity(self):
        return self.piece_count * self.per_box_count


def _positive_count(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{label} must be a positive integer")
    return value


def resolved_quantity_physical_demands(versions, *, per_box_counts=None):
    """Expand each physical sheet; presence comes only from canonical geometry.

    Multiplicities are supplied by the existing per-box metadata owner. A
    multipart logical item contributes its multiplicity to each actual sheet.
    No name grouping, topology multiplier, geometry rebuild or Q annotation.
    """
    counts = dict(per_box_counts or {})
    rows = []
    seen_versions = set()
    for version in tuple(versions):
        identity = str(version.version_id or "").strip()
        if not identity or identity in seen_versions:
            raise ValueError("quantity version ID must be non-empty and unique")
        seen_versions.add(identity)
        count = _positive_count(version.piece_count, "piece_count")
        seen_physical = set()
        parts = tuple(getattr(version.geometry, "parts", ()) or ())
        if not parts:
            raise ValueError(f"quantity version has no resolved physical parts: {identity}")
        for part in parts:
            source_id = str(part.part_key)
            multiplicity = _positive_count(counts.get(source_id, 1), "per_box_count")
            # Use the export owner's physical enumeration, including multipart
            # sheets, rather than maintaining another physical BOM list.
            for physical_id, render_data in resolved_physical_render_parts(
                SimpleNamespace(parts=(part,)),
                include_unreleased_source_flats=True,
            ):
                if physical_id in seen_physical:
                    raise ValueError(f"duplicate physical identity: {physical_id}")
                seen_physical.add(physical_id)
                rows.append(PhysicalPartDemand(
                    identity, source_id, physical_id, count, multiplicity, render_data
                ))
    if not seen_versions:
        raise ValueError("at least one resolved quantity version is required")
    return tuple(rows)
