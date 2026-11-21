"""Elf-scale ghost buggy — an original clamshell-style haunted-ride car for a
~30 cm shelf elf: a tall egg-shaped back, a hood that curls over the rider's
head, open sides above the armrests, a knee panel and a lap bar.

Construction (print-friendly by design):
  * Split down the middle into two mirrored halves. Each half prints lying on
    its OUTER side wall: every rim (back, hood, seat, knee panel, skirt) is a
    side profile extruded straight up to the centre plane, so nothing
    overhangs and nothing needs support.
  * The outer side gets a bed-side roundover that never goes flatter than
    45°, so the assembled buggy has soft, rounded shoulders.
  * Under the seat is a hollow pocket (saves ~40% plastic); the two pockets
    join into one cavity open at the bottom.
  * The lap bar is a separate octagonal rod (prints flat, no support) that
    drops into sockets on top of both armrest rails and is trapped when the
    halves are glued together.
"""

import math

import numpy as np
from manifold3d import CrossSection, OpType

from printlib.profile import load_printer
from printlib.shapes import (
    LAYER,
    difference,
    extrude_plain,
    hole,
    offset,
    on_bed,
    polygon,
    union,
)

P = load_printer()

META = {
    "title": "Elf-scale ghost buggy",
    "description": "Original clamshell-style haunted-ride car sized for a 30 cm shelf elf: two glue-together halves plus a drop-in lap bar.",
    "material": "PLA",
    "infill": 0.12,
    "supports": False,
    "notes": [
        "Default size ≈ 170 mm deep × 214 mm tall × 120 mm wide; the seat is ~56 mm up with ~147 mm of headroom "
        "under the hood and ~112 mm between the side walls — room for one elf (or two snug ones).",
        "Print each half lying on its outer side, as exported. One half per plate is easiest (~170 × 214 mm footprint, 60 mm tall).",
        "Classic look: black or dark-purple PLA, then a silver/gold paint pen along the hood edge and armrests. "
        "Silk or glow-in-the-dark PLA also looks great.",
        "Assembly: drop the lap bar's ends into the sockets on top of both armrest rails, push 1.75 mm filament pins "
        "(5 pieces, ~11 mm) into the holes on one half's centre face, press the halves together and glue (CA or PLA-safe glue).",
        "The flat centre faces are the glue joint; a light sand of the seam down the back and hood, then paint, hides it.",
        "Low infill is fine (it's a display piece); the walls give it the strength.",
    ],
}

PARAMS = {
    "scale": 1.0,        # 1.0 is elf-sized; 0.6 makes a ~13 cm desk ornament
    "width": 120.0,      # total outside width at scale 1 (each half is width/2 thick)
    "side_wall": 4.0,    # side wall thickness under the armrests
    "roundover": 12.0,   # radius of the 45°-limited roundover on the outer side edge
    "pin_d": 1.75,       # alignment pin = filament diameter
    "lap_bar": True,     # also export the drop-in lap bar
}

# Side profile (x = forward, y = up, back of the buggy at x≈0). Closed
# Catmull-Rom splines run through these points.
OUTER = [
    (22, 0), (152, 0), (152, 20), (166, 55), (170, 85), (162, 100), (150, 104),
    (132, 180), (122, 198), (95, 214), (55, 214), (22, 198), (6, 165), (2, 120),
    (8, 70), (18, 30),
]
# Rider space. Its front edge runs outside OUTER, which opens the front.
CAVITY = [
    (30, 56), (125, 56), (144, 62), (152, 92), (178, 104), (160, 182),
    (126, 176), (112, 192), (90, 203), (58, 203), (32, 190), (17, 162),
    (13, 120), (18, 80),
]
# Side opening above the armrest line, sweeping up into the hood cheeks.
OPENING = [(60, 98), (150, 95), (195, 100), (195, 240), (44, 240), (40, 172), (48, 122)]
# Hollow under the seat, open at the bottom.
POCKET = [(38, -2), (136, -2), (136, 30), (124, 40), (50, 40), (38, 30)]
RAIL_H = 10.0          # armrest rail band height in the side view
RAIL_T = 12.0          # rail thickness inward from the outer side
BAR = 5.0              # lap bar across-flats (octagon)
BAR_AT = (132, 90.0)   # lap bar socket centre (side view), in the armrest rail
PINS = [(29, 14), (145, 14), (87, 48), (75, 209), (8, 120)]  # skirt, seat pan, hood, back


def _spline(pts, n=16):
    """Closed Catmull-Rom spline through `pts`, `n` samples per segment."""
    p = np.asarray(pts, float)
    out = []
    for i in range(len(p)):
        p0, p1, p2, p3 = p[i - 1], p[i], p[(i + 1) % len(p)], p[(i + 2) % len(p)]
        for t in np.linspace(0, 1, n, endpoint=False):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    return np.array(out)


def _cs(pts, s, smooth=True):
    pts = _spline(pts) if smooth else np.asarray(pts, float)
    return polygon(pts * s)


def _rounded_bottom_slab(cs, h, r):
    """Extrude `cs` to height h with a rounded BED-side edge whose slope never
    passes 45° (a circular arc from 45° at the bed up to vertical), so it
    prints without support. Steps overlap so no faces meet at rounded heights."""
    zt = r / math.sqrt(2)                       # arc reaches vertical here
    steps = max(1, round(zt / LAYER))
    dz = zt / steps
    top = zt + 1.0
    parts = [extrude_plain(cs, h - zt).translate((0, 0, zt))]
    for i in range(steps):
        zc = (i + 0.5) * dz
        inset = r - math.sqrt(max(r * r - (zt - zc) ** 2, 0.0))
        layer = offset(cs, -inset)
        if not layer.is_empty():
            parts.append(extrude_plain(layer, top - i * dz).translate((0, 0, i * dz)))
    return union(parts)


def _add(parts):
    return CrossSection.batch_boolean(list(parts), OpType.Add)


def _octagon(across_flats):
    r = across_flats / 2 / math.cos(math.pi / 8)
    return CrossSection.circle(r, 8).rotate(22.5)


def _half(s, width, side_wall, roundover, pin_d):
    H, t, R = width / 2 * s, side_wall * s, roundover * s
    outer, cavity = _cs(OUTER, s), _cs(CAVITY, s)
    # The opening overshoots the cavity wall by 0.3 mm (under a line width) so
    # the two cutters never share a surface (that tears the exported STL).
    opening = _cs(OPENING, s, smooth=False) ^ offset(cavity, 0.3)
    pocket = _cs(POCKET, s, smooth=False)

    body = _rounded_bottom_slab(outer, H, R)
    big = H + 2
    cuts = [
        extrude_plain(cavity, big).translate((0, 0, t)),            # rider space above the side wall
        extrude_plain(opening, big + 2).translate((0, 0, -1)),       # open sides above the armrests
        extrude_plain(pocket, big).translate((0, 0, t)),             # hollow under the seat
    ]
    body = difference(body, cuts)

    # Armrest rail: a thicker band along the bottom edge of the side opening,
    # kept just inside the roundover (its deepest inset is 0.29 R) so the two
    # never share a surface.
    rail_band = (cavity - offset(opening, 0.3)) ^ offset(opening, RAIL_H * s) ^ offset(outer, -(0.3 * R + 1.0 * s))
    body = body + extrude_plain(rail_band, RAIL_T * s)

    # Lap-bar socket on top of the rail; alignment pins on the centre face.
    gap = P.tol("snug")
    sock_d = BAR * s / math.cos(math.pi / 8) + 2 * gap
    sock_depth = 7.0 * s
    sock = hole(sock_d, sock_depth, compensate=False).translate((BAR_AT[0] * s, BAR_AT[1] * s, RAIL_T * s - sock_depth))
    pins = [hole(pin_d + 2 * gap, 6.0).translate((x * s, y * s, H - 6.0)) for x, y in PINS]
    return on_bed(difference(body, [sock, *pins]))


def _lap_bar(s, width):
    """Octagonal rod lying on a flat face: spans the gap between the rail tops
    plus a socket's depth at each end, minus a little end clearance."""
    length = (width - 2 * RAIL_T) * s + 2 * 7.0 * s - 2 * 0.5
    rod = extrude_plain(_octagon(BAR * s), length)
    return on_bed(rod.rotate((0, 90, 0)))


def build(scale, width, side_wall, roundover, pin_d, lap_bar):
    half = _half(scale, width, side_wall, roundover, pin_d)
    parts = {"half-a": half, "half-b": on_bed(half.mirror((1, 0, 0)))}
    if lap_bar:
        parts["lap-bar"] = _lap_bar(scale, width)
    return parts
