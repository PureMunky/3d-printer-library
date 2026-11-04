"""Elf-scale light cycle — a low, rounded, modern sci-fi motorbike sized for a
~30 cm shelf elf (or any similar plush/figure) to ride.

Construction (print-friendly by design):
  * The side silhouette is a smooth closed spline wrapped around two wheels,
    so the body reads as one sleek low shell rather than a frame.
  * The bike is two mirrored side halves, each a flat slab printed lying on
    its inner (glue) face. The outer edge has a large quarter-round
    roundover, so the assembled bike has a soft, pill-shaped cross-section.
    A roundover on the *top* of a print only ever steps inward, so there are
    no overhangs and no supports.
  * The glow stripes follow the silhouette automatically (an inset band of
    the outline) and sit 0.8 mm proud of the flat top. Add a filament change
    at the slab-top height and they print in a second colour.
  * The halves line up with 1.75 mm filament offcuts as pins, then glue.
  * Optional `trail`: a free-standing curved "light ribbon" to set behind the
    bike for a scene. Print it in translucent / glow PLA.
"""

import math

import numpy as np
from manifold3d import CrossSection, OpType

from printlib.profile import load_printer
from printlib.shapes import (
    LAYER,
    circle,
    difference,
    extrude,
    extrude_plain,
    hole,
    offset,
    on_bed,
    polygon,
    rect,
    stroke,
    union,
)

P = load_printer()

META = {
    "title": "Elf-scale light cycle",
    "description": "Low, rounded, modern light cycle sized for a 30 cm shelf elf: two glue-together halves with two-colour glow stripes, plus an optional curved light-ribbon trail.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Default size ≈ 272 mm long × 79 mm tall × 42 mm wide; the seat dip is ~62 mm up for a ~30 cm elf to straddle (or lie forward, rider-style).",
        "Print both halves flat as exported (inner face on the bed). They fit on one plate together (~272 × 165 mm).",
        "Two-colour stripes: add a filament change / pause at the slab top (Z = half_width, 20.0 mm by default). "
        "In Anycubic Slicer Next: preview slider → right-click the first layer above 20.0 mm → Add color change (M600) or Add pause. "
        "Start in black, swap to cyan (classic) or orange (villain) PLA.",
        "The outer roundover prints as 0.2 mm stair steps; the last few layers before the flat top are wide, thin top-surface "
        "rings — normal, no support needed. 0.12–0.16 mm layers make the curve smoother if you want it glossier.",
        "Assembly: cut 3 pieces of 1.75 mm filament ~11 mm long, push them into the pin holes of one half, "
        "press the other half on, then glue. Superglue (CA) or a thin layer of PLA-safe glue.",
        "Trail ribbon: print in translucent or glow-in-the-dark PLA; it stands on its own behind the bike.",
    ],
}

PARAMS = {
    "scale": 1.0,          # 1.0 ≈ 272 mm long (elf-sized); 0.5 makes a desk toy
    "half_width": 20.0,    # slab thickness of each half (bike width ≈ 2× this) at scale 1
    "roundover": 7.0,      # radius of the rounded outer edge at scale 1
    "line_height": 0.8,    # raised glow-stripe height (4 layers)
    "line_width": 2.4,     # glow-stripe width at scale 1
    "pin_d": 1.75,         # alignment pin = filament diameter
    "trail": True,         # also export the free-standing light-ribbon trail
    "trail_height": 40.0,
}

WHEEL_R = 40.0
REAR = (50.0, 40.0)
FRONT = (222.0, 40.0)
# Wheel face detail radii — all inside the flat top, i.e. clear of the
# roundover even where the wheel is flattened for its contact patch.
GROOVE_R = 28.6
TYRE_R = 24.4
RIM_IN, RIM_OUT = 11.0, 22.6
HUB_R = 7.0

# Control points of the side silhouette (x along the bike, front at +x; y up),
# traced counter-clockwise from the tail. A closed Catmull-Rom spline runs
# through them, so the outline is smooth everywhere.
BODY = [
    (2, 44), (14, 64), (44, 77), (84, 73), (112, 63), (136, 60), (162, 63),
    (196, 74), (230, 80), (258, 70), (272, 50), (268, 30), (246, 14),
    (190, 10), (136, 9), (82, 10), (26, 15), (6, 28),
]

PINS = [REAR, FRONT, (136, 34)]


def _spline(pts, n=24):
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


def _add(parts):
    return CrossSection.batch_boolean(list(parts), OpType.Add)


def _ring(r_in, r_out, center):
    return (circle(2 * r_out) - circle(2 * r_in)).translate(center)


def _silhouette(s):
    body = polygon(_spline(BODY) * s)
    wheel = circle(2 * WHEEL_R * s)
    sil = _add([body, wheel.translate((REAR[0] * s, REAR[1] * s)), wheel.translate((FRONT[0] * s, FRONT[1] * s))])
    sil = offset(offset(sil, -4 * s), 4 * s)  # soften the wheel/body junctions
    # Flat contact patch under each wheel so it stands steady.
    return sil - rect(400 * s, 4 * s).translate((150 * s, 0))


def _rounded_slab(cs, h, r):
    """Extrude `cs` to height h with a quarter-round top edge of radius r,
    built as layer-height steps (how the printer makes it anyway). Steps
    overlap down to mid-body so no faces meet at float-rounded heights."""
    r = min(r, h - 1.0)
    z0 = h - r
    mid = z0 / 2
    parts = [extrude(cs, z0, bottom_chamfer=P.design["first_layer_chamfer"])]
    steps = max(1, round(r / LAYER))
    for i in range(steps):
        zc = z0 + (i + 0.5) * r / steps             # sample the arc mid-step
        inset = r - math.sqrt(max(r * r - (zc - z0) ** 2, 0.0))
        top = h if i == steps - 1 else z0 + (i + 1) * r / steps
        layer = offset(cs, -max(inset, 0.05))
        if not layer.is_empty():
            parts.append(extrude_plain(layer, top - mid).translate((0, 0, mid)))
    return union(parts)


def _half(s, half_width, roundover, line_height, line_width, pin_d):
    T, R = half_width * s, roundover * s
    sil = _silhouette(s)
    body = _rounded_slab(sil, T, R)

    centres = [(REAR[0] * s, REAR[1] * s), (FRONT[0] * s, FRONT[1] * s)]
    groove_w, groove_d, recess_d = 1.4 * s, 1.0 * s, 1.2 * s
    cuts = []
    for c in centres:
        g = _ring(GROOVE_R * s, GROOVE_R * s + groove_w, c)            # wheel / body split line
        cuts.append(extrude_plain(g, groove_d + 0.02).translate((0, 0, T - groove_d)))
        r = _ring(RIM_IN * s, RIM_OUT * s, c)                          # recessed rim
        cuts.append(extrude_plain(r, recess_d + 0.02).translate((0, 0, T - recess_d)))
    pin_depth = min(6.0, T - 3.0)
    for px, py in PINS:
        cuts.append(hole(pin_d + 2 * P.tol("snug"), pin_depth).translate((px * s, py * s, 0)))
    body = difference(body, cuts)

    # Glow stripe = a band following the outline just inside the roundover,
    # kept on the upper body (tail → seat → nose) plus a belly run.
    lw = line_width * s
    inset = R + 2.5 * s
    band = offset(sil, -inset) - offset(sil, -(inset + lw))
    upper = rect(400 * s, 200 * s).translate((150 * s, (WHEEL_R + 100) * s))
    belly = rect(70 * s, 30 * s).translate(((REAR[0] + FRONT[0]) / 2 * s, 0))
    glow = band ^ _add([upper, belly])
    for c in centres:
        glow = glow - _ring((GROOVE_R - 1.0) * s, (GROOVE_R + 1.0) * s + groove_w, c)
        glow = glow + _ring(TYRE_R * s, TYRE_R * s + lw, c)            # tyre ring
        glow = glow + _ring(HUB_R * s, HUB_R * s + lw, c)              # hub ring
    glow = glow.simplify(1e-3)
    sink = 0.3  # sink stripes into the slab so the union is solid
    body = body + extrude_plain(glow, sink + line_height).translate((0, 0, T - sink))
    return on_bed(body)


def _trail(s, h):
    """A gently curving free-standing light ribbon with a stabilising foot."""
    t, h = 3.2, h * s
    xs = np.linspace(0, 160 * s, 60)
    pts = np.column_stack([xs, 22 * s * np.sin(xs / (160 * s) * 1.5 * math.pi)])
    wall = extrude(stroke(pts, t, segments=16), h, bottom_chamfer=P.design["first_layer_chamfer"])
    foot = extrude(stroke(pts, 12.0, segments=24), 2.0, bottom_chamfer=P.design["first_layer_chamfer"])
    return on_bed(union(wall, foot))


def build(scale, half_width, roundover, line_height, line_width, pin_d, trail, trail_height):
    half = _half(scale, half_width, roundover, line_height, line_width, pin_d)
    parts = {"half-a": half, "half-b": on_bed(half.mirror((1, 0, 0)))}
    if trail:
        parts["trail"] = _trail(scale, trail_height)
    return parts
