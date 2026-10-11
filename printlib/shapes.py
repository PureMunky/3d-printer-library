"""Modeling helpers on top of manifold3d, with FDM-friendly defaults.

Conventions
-----------
* Units are millimetres. +Z is up; the bed is the plane z = 0.
* Solids returned here sit on the bed (z >= 0) and are centred on X/Y
  unless stated otherwise — call :func:`on_bed` after boolean work to be sure.
* "Cutter" helpers (holes, nut traps, ...) return solids meant to be
  subtracted. They overshoot faces by ``EPS`` so subtractions never leave
  zero-thickness skins.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

import numpy as np
from manifold3d import CrossSection, FillRule, JoinType, Manifold, set_circular_segments

from .profile import load_printer

EPS = 0.01  # overshoot for cutters

# Smooth enough for printing without exploding triangle counts.
set_circular_segments(96)

_P = load_printer()
LAYER = float(_P.design["layer_height"])
HOLE_COMP = float(_P.design["hole_compensation"])


# --------------------------------------------------------------------------- #
# Placement
# --------------------------------------------------------------------------- #
def bounds(m: Manifold) -> tuple[np.ndarray, np.ndarray]:
    b = m.bounding_box()
    return np.array(b[:3]), np.array(b[3:])


def size(m: Manifold) -> np.ndarray:
    lo, hi = bounds(m)
    return hi - lo


def on_bed(m: Manifold, center: bool = True) -> Manifold:
    """Drop a solid onto z = 0 and (optionally) centre it on X/Y."""
    lo, hi = bounds(m)
    dx, dy = (-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2) if center else (0.0, 0.0)
    return m.translate((dx, dy, -lo[2]))


def union(*parts: Manifold | Iterable[Manifold]) -> Manifold:
    flat: list[Manifold] = []
    for p in parts:
        flat.extend([p] if isinstance(p, Manifold) else list(p))
    return Manifold.batch_boolean(flat, _op("Add")) if flat else Manifold()


def difference(base: Manifold, *cutters: Manifold | Iterable[Manifold]) -> Manifold:
    cut = union(*cutters)
    return base - cut if not cut.is_empty() else base


def _op(name: str):
    from manifold3d import OpType

    return getattr(OpType, name)


def arrange(parts: Sequence[Manifold], gap: float = 5.0) -> Manifold:
    """Lay several parts side by side along X (for a single multi-part plate)."""
    placed, x = [], 0.0
    for p in parts:
        p = on_bed(p, center=False)
        lo, hi = bounds(p)
        placed.append(p.translate((x - lo[0], -(lo[1] + hi[1]) / 2, 0)))
        x += (hi[0] - lo[0]) + gap
    return on_bed(union(placed))


def pack(parts: Sequence[Manifold], width: float = 300.0, gap: float = 4.0) -> Manifold:
    """Shelf-pack parts into rows no wider than `width` (one multi-part plate).

    Parts keep their order; tallest-first input packs tighter. Raises if the
    result won't fit the printer's usable bed.
    """
    placed, x, y, row_h = [], 0.0, 0.0, 0.0
    for p in parts:
        p = on_bed(p, center=False)
        lo, hi = bounds(p)
        w, h = hi[0] - lo[0], hi[1] - lo[1]
        if x > 0 and x + w > width:
            x, y, row_h = 0.0, y - row_h - gap, 0.0
        placed.append(p.translate((x - lo[0], y - hi[1], 0)))
        x += w + gap
        row_h = max(row_h, h)
    plate = on_bed(union(placed))
    ext = size(plate)
    ux, uy, _ = _P.usable_volume
    if ext[0] > ux or ext[1] > uy:
        raise ValueError(f"packed plate {ext[0]:.0f} x {ext[1]:.0f} mm exceeds usable bed {ux} x {uy}")
    return plate


# --------------------------------------------------------------------------- #
# 2D profiles
# --------------------------------------------------------------------------- #
def rect(x: float, y: float, r: float = 0.0) -> CrossSection:
    """Centred rectangle, optionally with rounded corners of radius r."""
    if r <= 0:
        return CrossSection.square((x, y), center=True)
    r = min(r, x / 2 - 1e-3, y / 2 - 1e-3)
    return offset(CrossSection.square((x - 2 * r, y - 2 * r), center=True), r)


def circle(d: float) -> CrossSection:
    return CrossSection.circle(d / 2)


def offset(cs: CrossSection, delta: float, join: JoinType = JoinType.Round) -> CrossSection:
    """Grow (+) or shrink (-) a profile. Always use this instead of
    ``cs.offset``: Clipper can leave vertices ~1e-8 mm apart where arcs meet
    lines, which become zero-length edges that tear the exported STL."""
    return cs.offset(delta, join).simplify(1e-4)


def polygon(points: Sequence[Sequence[float]]) -> CrossSection:
    pts = np.asarray(points, dtype=float)
    if _signed_area(pts) < 0:
        pts = pts[::-1]
    return CrossSection([pts])


def _signed_area(pts: np.ndarray) -> float:
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def text2d(
    s: str,
    size: float = 10.0,
    font: str = "DejaVu Sans",
    weight: str = "bold",
    halign: str = "center",
    valign: str = "center",
) -> CrossSection:
    """Text outline as a CrossSection. `size` is roughly the cap height in mm.

    Keep strokes >= design.min_feature (0.8 mm): for bold DejaVu that means
    size >= ~6 mm for raised text.
    """
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath

    # TextPath size is the em size; cap height of DejaVu is ~0.73 em.
    tp = TextPath((0, 0), s, size=size / 0.73, prop=FontProperties(family=font, weight=weight))
    polys = [np.asarray(p, dtype=float) for p in tp.to_polygons(closed_only=True) if len(p) >= 3]
    if not polys:
        return CrossSection()
    cs = CrossSection(polys, FillRule.EvenOdd)
    (x0, y0), (x1, y1) = np.array(cs.bounds()).reshape(2, 2)
    dx = {"left": -x0, "center": -(x0 + x1) / 2, "right": -x1}[halign]
    dy = {"bottom": -y0, "center": -(y0 + y1) / 2, "top": -y1}[valign]
    return cs.translate((dx, dy))


def stroke(points: Sequence[Sequence[float]], width: float, segments: int = 16) -> CrossSection:
    """Open polyline -> filled stroke of uniform `width` with round caps/joins.

    `segments` sides per round cap: ~10 is plenty for 1 mm strokes (keeps big
    lettered parts' STLs small); raise it for wide strokes."""
    pts = np.asarray(points, dtype=float)
    parts = [CrossSection.circle(width / 2, segments).translate(tuple(pts[0]))]
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        length = math.hypot(x1 - x0, y1 - y0)
        if length < 1e-9:
            continue
        seg = CrossSection.square((length, width)).translate((0, -width / 2))
        parts.append(seg.rotate(math.degrees(math.atan2(y1 - y0, x1 - x0))).translate((x0, y0)))
        parts.append(CrossSection.circle(width / 2, segments).translate((x1, y1)))
    return CrossSection.batch_boolean(parts, _op("Add"))


_HERSHEY = {}


def _hershey(font: str):
    if font not in _HERSHEY:
        from HersheyFonts import HersheyFonts

        f = HersheyFonts()
        f.load_default_font(font)
        f.normalize_rendering(100.0)
        ys = [y for seg in f.lines_for_text("H") for _, y in seg]
        _HERSHEY[font] = (f, max(ys) - min(ys))  # font object, cap height in font units
    return _HERSHEY[font]


def stroke_text(
    s: str,
    cap: float = 4.4,
    width: float | None = None,
    gap: float | None = None,
    font: str = "futural",
    segments: int = 12,
    halign: str = "center",
    valign: str = "center",
) -> CrossSection:
    """Single-stroke (Hershey) text with a uniform stroke and controlled spacing.

    Use instead of text2d() wherever strokes and gaps must clear a printable
    minimum (raised or engraved small text): every stroke is exactly `width`
    (default: the profile's min_wall) and glyphs are spaced so the ink gap
    between letters is `gap` (default: the same). Keep `cap` >= ~4.5 x width
    so the gaps inside letters like B/E/8 clear it too.
    """
    import unicodedata

    # Hershey fonts are ASCII: fold accents (BOÖTES -> BOOTES) rather than drop letters.
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    w = width if width is not None else float(_P.design["min_wall"])
    g = gap if gap is not None else w
    f, cap_units = _hershey(font)
    k = cap / cap_units
    parts, x = [], 0.0
    for ch in s:
        if ch == " ":
            x += 0.55 * cap
            continue
        segs = [((a[0] * k, a[1] * k), (b[0] * k, b[1] * k)) for a, b in f.lines_for_text(ch)]
        if not segs:
            x += 0.55 * cap
            continue
        xs = [p[0] for seg in segs for p in seg]
        x0 = min(xs)
        for a, b in segs:
            parts.append(stroke([(a[0] - x0 + x, a[1]), (b[0] - x0 + x, b[1])], w, segments))
        x += (max(xs) - x0) + w + g
    if not parts:
        return CrossSection()
    cs = CrossSection.batch_boolean(parts, _op("Add")).simplify(1e-4)
    bx0, by0, bx1, by1 = cs.bounds()
    dx = {"left": -bx0, "center": -(bx0 + bx1) / 2, "right": -bx1}[halign]
    dy = {"bottom": -by0, "center": -(by0 + by1) / 2, "top": -by1}[valign]
    return cs.translate((dx, dy))


# --------------------------------------------------------------------------- #
# 3D primitives (on the bed, centred on X/Y)
# --------------------------------------------------------------------------- #
def extrude(cs: CrossSection, h: float, bottom_chamfer: float = 0.0, top_chamfer: float = 0.0) -> Manifold:
    """Extrude a profile, optionally chamfering the bottom/top edges.

    The chamfer is built as layer-height steps, which is exactly how the
    printer reproduces it anyway, and works for any (non-convex) profile.
    Use bottom_chamfer = design.first_layer_chamfer (0.4) on parts whose
    bottom edge must stay crisp/flush — it hides elephant's foot.
    """
    cs = cs.simplify(1e-4)  # 2D booleans can also leave ~1e-8 mm vertex pairs
    body_lo, body_hi = bottom_chamfer, h - top_chamfer
    parts = [extrude_plain(cs, body_hi - body_lo).translate((0, 0, body_lo))]
    for c, z0, direction in ((bottom_chamfer, 0.0, 1), (top_chamfer, body_hi, -1)):
        if c <= 0:
            continue
        steps = max(1, round(c / LAYER))
        dz = c / steps
        for i in range(steps):
            # bottom: inset shrinks as we go up; top: inset grows as we go up
            frac = (steps - i) / steps if direction == 1 else (i + 1) / steps
            inset = c * frac
            layer = offset(cs, -inset)
            if layer.is_empty():
                continue
            parts.append(extrude_plain(layer, dz).translate((0, 0, z0 + i * dz)))
    return union(parts)


def extrude_plain(cs: CrossSection, h: float) -> Manifold:
    return Manifold.extrude(cs, h)


def box(x: float, y: float, z: float, r: float = 0.0, bottom_chamfer: float = 0.0, top_chamfer: float = 0.0) -> Manifold:
    """Box centred on X/Y sitting on the bed; r rounds the vertical edges."""
    return extrude(rect(x, y, r), z, bottom_chamfer, top_chamfer)


def cylinder(d: float, h: float, d2: float | None = None) -> Manifold:
    return Manifold.cylinder(h, d / 2, (d2 if d2 is not None else d) / 2)


def sphere(d: float) -> Manifold:
    return Manifold.sphere(d / 2)


# --------------------------------------------------------------------------- #
# Cutters (subtract these)
# --------------------------------------------------------------------------- #
def hole(d: float, depth: float, compensate: bool = True) -> Manifold:
    """Vertical hole cutter from z = -EPS up to depth + EPS.

    Vertical holes print undersized; compensate adds design.hole_compensation
    to the radius so a 3 mm hole actually measures ~3 mm.
    """
    r = d / 2 + (HOLE_COMP if compensate else 0.0)
    return Manifold.cylinder(depth + 2 * EPS, r).translate((0, 0, -EPS))


def teardrop(d: float, length: float, axis: str = "x", compensate: bool = True) -> Manifold:
    """Horizontal hole cutter with a 45° pointed roof so it prints without support.

    Centred on the origin, running along `axis` ("x" or "y").
    """
    r = d / 2 + (HOLE_COMP if compensate else 0.0)
    tip = r * math.sqrt(2)
    roof = polygon([(-r / math.sqrt(2), r / math.sqrt(2)), (0, tip), (r / math.sqrt(2), r / math.sqrt(2)), (0, 0)])
    profile = CrossSection.circle(r) + roof  # profile in XY, point toward +Y
    solid = Manifold.extrude(profile, length + 2 * EPS).translate((0, 0, -(length / 2 + EPS)))
    # Map profile +Y -> world +Z, extrusion Z -> world axis.
    solid = solid.rotate((90, 0, 0))  # profile Y->Z, extrusion -> -Y
    if axis == "x":
        solid = solid.rotate((0, 0, 90))
    elif axis != "y":
        raise ValueError("axis must be 'x' or 'y'")
    return solid


# ISO metric hardware, mm. clearance = free-fit hole, head = socket-cap head
# diameter, nut = hex nut across flats, insert = typical heat-set insert hole.
METRIC = {
    "M2": dict(clearance=2.4, head=3.8, head_h=2.0, nut=4.0, nut_h=1.6, insert=3.2),
    "M2.5": dict(clearance=2.9, head=4.5, head_h=2.5, nut=5.0, nut_h=2.0, insert=3.6),
    "M3": dict(clearance=3.4, head=5.5, head_h=3.0, nut=5.5, nut_h=2.4, insert=4.0),
    "M4": dict(clearance=4.5, head=7.0, head_h=4.0, nut=7.0, nut_h=3.2, insert=5.6),
    "M5": dict(clearance=5.5, head=8.5, head_h=5.0, nut=8.0, nut_h=4.0, insert=6.4),
    "M6": dict(clearance=6.6, head=10.0, head_h=6.0, nut=10.0, nut_h=5.0, insert=8.0),
}


def screw_hole(size: str, depth: float, counterbore: float = 0.0, countersink: bool = False) -> Manifold:
    """Clearance hole for a metric screw, entering from the top (z = depth).

    counterbore: depth of a socket-head pocket at the top. countersink: 90° cone.
    """
    s = METRIC[size]
    cut = hole(s["clearance"], depth, compensate=False)
    if counterbore > 0:
        cut += hole(s["head"] + 0.6, counterbore, compensate=False).translate((0, 0, depth - counterbore))
    if countersink:
        r_top = s["head"] / 2 + 0.2
        cone_h = r_top - s["clearance"] / 2
        cut += Manifold.cylinder(cone_h + EPS, s["clearance"] / 2, r_top + EPS).translate((0, 0, depth - cone_h))
    return cut


def nut_trap(size: str, depth: float | None = None, clearance: float = 0.15) -> Manifold:
    """Hexagonal pocket for a metric nut from z = -EPS (flats aligned to X)."""
    s = METRIC[size]
    flats = s["nut"] + 2 * clearance
    r = flats / math.sqrt(3)  # circumradius
    h = (depth if depth is not None else s["nut_h"] + 0.3) + 2 * EPS
    return Manifold.cylinder(h, r, r, circular_segments=6).translate((0, 0, -EPS))


def insert_hole(size: str, depth: float) -> Manifold:
    """Pilot hole for a brass heat-set insert (insert pressed in from the top)."""
    return hole(METRIC[size]["insert"], depth, compensate=False)


# --------------------------------------------------------------------------- #
# Decoration
# --------------------------------------------------------------------------- #
def emboss(base: Manifold, cs: CrossSection, z_top: float, height: float | None = None) -> Manifold:
    """Raise a 2D shape (e.g. text2d) on top of a flat face at z_top."""
    h = height if height is not None else float(_P.design["emboss_height"])
    return base + Manifold.extrude(cs, h).translate((0, 0, z_top))


def engrave(base: Manifold, cs: CrossSection, z_top: float, depth: float | None = None) -> Manifold:
    """Cut a 2D shape down into a flat face at z_top."""
    d = depth if depth is not None else float(_P.design["emboss_height"])
    return base - Manifold.extrude(cs, d + EPS).translate((0, 0, z_top - d))


_FACES = {
    "+x": ((1, 0, 0), (0, 0, 1)),
    "-x": ((-1, 0, 0), (0, 0, 1)),
    "+y": ((0, 1, 0), (0, 0, 1)),
    "-y": ((0, -1, 0), (0, 0, 1)),
    "+z": ((0, 0, 1), (0, 1, 0)),
    "-z": ((0, 0, -1), (0, -1, 0)),
}


def face_frame(base: Manifold, face: str, offset: Sequence[float] = (0.0, 0.0)) -> np.ndarray:
    """3x4 transform mapping a local 2D frame onto a bounding-box face.

    Local +X is "right" and +Y "up" for someone looking at that face from
    outside; local +Z is the outward normal; the origin is the face centre
    (plus `offset` in local X/Y).
    """
    n, u = (np.array(v, float) for v in _FACES[face])
    r = np.cross(u, n)
    lo, hi = bounds(base)
    c = (lo + hi) / 2
    axis = int(np.argmax(np.abs(n)))
    c[axis] = hi[axis] if n[axis] > 0 else lo[axis]
    c = c + offset[0] * r + offset[1] * u
    return np.column_stack([r, u, n, c])


def label_face(
    base: Manifold,
    cs: CrossSection,
    face: str = "+z",
    depth: float | None = None,
    raised: bool = False,
    offset: Sequence[float] = (0.0, 0.0),
) -> Manifold:
    """Engrave (default) or emboss a 2D shape such as text2d() onto a flat
    bounding-box face: "+x", "-x", "+y", "-y", "+z" or "-z".

    Engraving on vertical faces prints cleanly; prefer it over embossing there.
    Avoid "-z" (the bed side) except for mirrored bottom markings.
    """
    d = depth if depth is not None else float(_P.design["emboss_height"])
    if raised:
        tool = Manifold.extrude(cs, d + EPS).translate((0, 0, -EPS))
        return base + tool.transform(face_frame(base, face, offset))
    tool = Manifold.extrude(cs, d + EPS).translate((0, 0, -d))
    return base - tool.transform(face_frame(base, face, offset))
