"""Printability checks for a mesh against the printer profile.

`check_mesh` returns a :class:`Report` of findings, each tagged
ERROR (won't print / will fail), WARN (likely problem, decide consciously)
or INFO (useful facts). It is deliberately heuristic: it catches the common
FDM failure modes (not watertight, off the bed, too big, unsupported
overhangs, long bridges, walls too thin to slice, tiny bed contact) so they
are fixed in the model rather than discovered at layer 40.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import trimesh
from manifold3d import JoinType

from .meshio import to_manifold, to_trimesh
from .profile import Printer, load_printer

ERROR, WARN, INFO = "ERROR", "WARN", "INFO"


@dataclass
class Finding:
    level: str
    code: str
    message: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.code}: {self.message}"


@dataclass
class Report:
    name: str
    findings: list[Finding] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def add(self, level: str, code: str, message: str) -> None:
        self.findings.append(Finding(level, code, message))

    @property
    def ok(self) -> bool:
        return not any(f.level == ERROR for f in self.findings)

    def by_level(self, level: str) -> list[Finding]:
        return [f for f in self.findings if f.level == level]

    def to_text(self) -> str:
        lines = [f"Printability report: {self.name}", ""]
        for k, v in self.stats.items():
            lines.append(f"  {k:<22} {v}")
        lines.append("")
        order = {ERROR: 0, WARN: 1, INFO: 2}
        for f in sorted(self.findings, key=lambda f: order[f.level]):
            lines.append(str(f))
        lines.append("")
        lines.append("RESULT: " + ("PRINTABLE" if self.ok else "NOT PRINTABLE — fix errors above"))
        return "\n".join(lines)

    def to_markdown(self) -> str:
        lines = ["| Stat | Value |", "|---|---|"]
        lines += [f"| {k} | {v} |" for k, v in self.stats.items()]
        lines.append("")
        if self.findings:
            icon = {ERROR: "❌", WARN: "⚠️", INFO: "ℹ️"}
            order = {ERROR: 0, WARN: 1, INFO: 2}
            for f in sorted(self.findings, key=lambda f: order[f.level]):
                lines.append(f"- {icon[f.level]} **{f.code}** — {f.message}")
        return "\n".join(lines)


def check_mesh(
    mesh: trimesh.Trimesh,
    name: str = "model",
    printer: Printer | None = None,
    material: str = "PLA",
    infill: float = 0.15,
    supports: bool = False,
) -> Report:
    p = printer or load_printer()
    d = p.design
    mesh = to_trimesh(mesh)
    r = Report(name)

    lo, hi = mesh.bounds
    ext = hi - lo
    r.stats["dimensions (mm)"] = f"{ext[0]:.2f} x {ext[1]:.2f} x {ext[2]:.2f}"
    r.stats["triangles"] = f"{len(mesh.faces):,}"

    # --- mesh validity ------------------------------------------------------
    if len(mesh.faces) == 0:
        r.add(ERROR, "empty", "Mesh has no triangles.")
        return r
    watertight = mesh.is_watertight
    if not watertight:
        r.add(ERROR, "not-watertight", "Mesh has holes/open edges; slicers may produce garbage. Rebuild as a closed solid.")
    if not mesh.is_winding_consistent:
        r.add(ERROR, "winding", "Inconsistent face winding (flipped normals).")
    if watertight and mesh.volume < 0:
        r.add(ERROR, "inside-out", "Mesh is inside-out (negative volume).")
    bodies = mesh.split(only_watertight=False)
    if len(bodies) > 1:
        r.add(INFO, "multi-body", f"{len(bodies)} separate bodies — fine for a plate of parts; make sure each one touches the bed.")
        floating = [b for b in bodies if b.bounds[0][2] - lo[2] > 0.05]
        if floating:
            r.add(ERROR, "floating-body", f"{len(floating)} body(ies) do not touch the bed (lowest at z={min(b.bounds[0][2] for b in floating):.2f}).")
    if ext.min() < 1e-6:
        r.add(ERROR, "flat", "Model has zero thickness in one axis.")
        return r

    # --- units / scale sanity ----------------------------------------------
    if ext.max() < 2.0:
        r.add(WARN, "tiny", "Largest dimension < 2 mm — was this exported in metres or inches? STL must be in mm.")
    if ext.max() > 10 * max(p.build_volume):
        r.add(ERROR, "huge", "Model is >10x the build volume — probably exported in microns or wrong units.")

    # --- placement ----------------------------------------------------------
    if abs(lo[2]) > 0.01:
        r.add(WARN, "not-on-bed", f"Lowest point is z={lo[2]:.3f}, not 0. Use `printlib place` (slicers usually drop it anyway).")

    # --- fits the printer ---------------------------------------------------
    uv = np.array(p.usable_volume, dtype=float)
    fits_xy = (ext[0] <= uv[0] and ext[1] <= uv[1]) or (ext[1] <= uv[0] and ext[0] <= uv[1])
    if not fits_xy or ext[2] > uv[2]:
        diag_ok = ext[2] <= uv[2] and _fits_rotated(ext[0], ext[1], uv[0], uv[1])
        if diag_ok:
            r.add(WARN, "fits-diagonally", "Only fits if rotated on the bed (diagonal) — rotate in the slicer.")
        else:
            r.add(ERROR, "too-big", f"{ext.round(1).tolist()} exceeds usable volume {uv.tolist()} — split the model or scale it.")
    else:
        r.add(INFO, "fits", f"Fits the {p.name} usable volume {uv.astype(int).tolist()}.")

    # --- volume / material ----------------------------------------------------
    if watertight:
        from .estimate import estimate

        est = estimate(mesh, printer=p, material=material, infill=infill)
        r.stats["volume (cm³)"] = f"{mesh.volume / 1000:.2f}"
        r.stats[f"est. {material} (g)"] = f"{est['grams']:.1f}"
        r.stats["est. filament (m)"] = f"{est['meters']:.2f}"
        r.stats["est. print time"] = est["time_str"]

    # --- overhangs ----------------------------------------------------------
    normals, areas, centers = mesh.face_normals, mesh.area_faces, mesh.triangles_center
    max_oh = math.radians(float(d["max_overhang_deg"]))
    # A face needs support when its normal points down more steeply than the
    # overhang limit (measured from vertical). Faces resting on the bed don't.
    on_bed = centers[:, 2] < lo[2] + 0.05
    down = normals[:, 2] < -math.sin(max_oh) - 1e-6
    oh_mask = down & ~on_bed
    oh_area = float(areas[oh_mask].sum())
    r.stats["bed contact (mm²)"] = f"{float(areas[on_bed & (normals[:, 2] < -0.99)].sum()):.0f}"
    r.stats["overhang area (mm²)"] = f"{oh_area:.0f}"
    if oh_area > 1.0:
        regions = _regions(mesh, oh_mask)
        bridges, steep, minor = [], [], 0.0
        for idx in regions:
            reg_area = float(areas[idx].sum())
            flat = np.all(normals[idx, 2] < -0.99)
            # Narrow ledges (layer-height stair steps from chamfers, tops of
            # small engraved letters/holes) are bridged trivially by the printer.
            if reg_area < 4.0 or _min_span(mesh, idx) < 2 * float(d["line_width"]) + 0.1:
                minor += reg_area
            elif flat:
                bridges.append((idx, reg_area))
            else:
                steep.append((idx, reg_area))
        if minor > 0:
            r.add(INFO, "minor-overhang", f"{minor:.0f} mm² of tiny ledges/roofs (stair steps, small holes, lettering) — print fine unsupported.")
        max_bridge = float(d["max_bridge"])
        ok_spans = []
        for idx, area in bridges:
            span = _min_span(mesh, idx)
            z = centers[idx, 2].mean()
            if span > max_bridge:
                lvl = INFO if supports else WARN
                r.add(lvl, "long-bridge", f"Flat downward face at z≈{z:.1f} spans {span:.1f} mm (> {max_bridge:.0f} mm). Needs support, a chamfer/arch, or a split.")
            else:
                ok_spans.append(span)
        if ok_spans:
            r.add(INFO, "bridge", f"{len(ok_spans)} bridge(s), longest {max(ok_spans):.1f} mm — OK with good cooling.")
        if steep:
            total = sum(a for _, a in steep)
            zs = sorted({round(float(centers[i, 2].mean()), 1) for i, _ in steep})
            lvl = INFO if supports else WARN
            r.add(lvl, "overhang", f"{total:.0f} mm² steeper than {d['max_overhang_deg']}° in {len(steep)} region(s) (z≈{_fmt_list(zs)}). Add supports, chamfer to 45°, or re-orient (`printlib orient`).")
    else:
        r.add(INFO, "no-supports", "No overhangs beyond the limit — prints without supports.")

    # --- thin walls -----------------------------------------------------------
    if watertight:
        _check_thin(mesh, r, p)

    # --- stability ------------------------------------------------------------
    contact = float(areas[on_bed & (normals[:, 2] < -0.99)].sum())
    if contact < 1.0:
        r.add(ERROR, "no-bed-contact", "No flat face on the bed — re-orient onto a flat face or add a flat base.")
    else:
        width = math.sqrt(contact)
        ratio = width / ext[2] if ext[2] > 0 else 1
        if ratio < float(d["min_bed_contact_ratio"]):
            r.add(WARN, "tippy", f"Tall ({ext[2]:.0f} mm) with small footprint ({contact:.0f} mm²). Use a brim (5–8 mm) or widen the base.")
        if ext[0] > 150 or ext[1] > 150:
            if material.upper() in ("ABS", "ASA"):
                r.add(WARN, "warp-risk", f"Large {material} part on an open-frame printer — expect corner lift. Brim + draft shield, or switch to PETG.")
    return r


def _fits_rotated(a: float, b: float, W: float, H: float) -> bool:
    for deg in range(0, 91, 1):
        t = math.radians(deg)
        w = a * math.cos(t) + b * math.sin(t)
        h = a * math.sin(t) + b * math.cos(t)
        if w <= W and h <= H:
            return True
    return False


def _regions(mesh: trimesh.Trimesh, mask: np.ndarray) -> list[np.ndarray]:
    idx = np.nonzero(mask)[0]
    if len(idx) == 0:
        return []
    adj = mesh.face_adjacency
    keep = mask[adj[:, 0]] & mask[adj[:, 1]] if len(adj) else np.zeros(0, bool)
    groups = trimesh.graph.connected_components(adj[keep], nodes=idx, min_len=1)
    return [np.asarray(g) for g in groups]


def _min_span(mesh: trimesh.Trimesh, faces: np.ndarray) -> float:
    """Shortest unsupported span of a flat region ≈ its narrowest XY width."""
    from shapely.geometry import Polygon
    from shapely.ops import unary_union

    tris = mesh.triangles[faces][:, :, :2]
    poly = unary_union([Polygon(t) for t in tris if Polygon(t).area > 1e-9])
    if poly.is_empty:
        return 0.0
    # Narrowest width = 2 * largest inscribed radius.
    try:
        from shapely import maximum_inscribed_circle

        line = maximum_inscribed_circle(poly)
        return 2 * float(line.length)
    except Exception:
        rect = poly.minimum_rotated_rectangle
        xs, ys = rect.exterior.coords.xy
        e = [math.dist((xs[i], ys[i]), (xs[i + 1], ys[i + 1])) for i in range(2)]
        return min(e)


def _check_thin(mesh: trimesh.Trimesh, r: Report, p: Printer) -> None:
    """Slice the part and look for features narrower than min_wall.

    Morphological opening: erode each slice by min_wall/2 then dilate back.
    Whatever disappears is thinner than min_wall and will likely be dropped
    or under-extruded by the slicer.
    """
    try:
        solid = to_manifold(mesh)
    except ValueError:
        return
    min_wall = float(p.design["min_wall"])
    lo, hi = mesh.bounds
    h = hi[2] - lo[2]
    n = int(min(60, max(8, h / 0.5)))
    zs = np.linspace(lo[2] + 0.1, hi[2] - 0.1, n) if h > 0.3 else [lo[2] + h / 2]
    thin_z, worst = [], 0.0
    for z in zs:
        cs = solid.slice(float(z))
        a = cs.area()
        if a <= 0:
            continue
        opened = cs.offset(-min_wall / 2, JoinType.Round).offset(min_wall / 2, JoinType.Round)
        lost = a - opened.area()
        if lost > max(0.5, 0.02 * a):
            thin_z.append(round(float(z), 1))
            worst = max(worst, lost / a)
    if thin_z:
        r.add(
            WARN,
            "thin-wall",
            f"Features thinner than {min_wall} mm at z≈{_fmt_list(thin_z)} (up to {worst:.0%} of that slice). "
            f"Thicken to ≥{p.design['recommended_wall']} mm or they may not print.",
        )


def _fmt_list(vals: list, n: int = 6) -> str:
    vals = list(vals)
    s = ", ".join(str(v) for v in vals[:n])
    return s + (f", … (+{len(vals) - n})" if len(vals) > n else "")
