"""Elf-scale light cycle — a modern replica-style light cycle sized for a
~30 cm shelf elf (or any similar plush/figure) to ride: big hubless wheels
with glowing tyre bands, fender shells hugging each wheel, a low spine with a
seat dip, and swoosh accents.

Construction (print-friendly by design):
  * The side silhouette is the union of two tyres, two offset fender shells
    and a smooth spline spine, filleted together. The wheel centres are open
    straight through (vertical holes as printed, so no supports).
  * The bike is two mirrored side halves, each a flat slab printed lying on
    its inner (glue) face. The outer edge has a large quarter-round
    roundover, so the assembled bike has a soft, pill-shaped cross-section.
    A roundover on the *top* of a print only ever steps inward, so there are
    no overhangs and no supports.
  * The tyre bands and tapered swooshes sit 0.8 mm proud of the flat top. Add a filament change
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
    "description": "Replica-style light cycle sized for a 30 cm shelf elf: hubless glowing wheels, two glue-together halves with two-colour glow accents, plus an optional curved light-ribbon trail.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Default size ≈ 274 mm long × 89 mm tall × 42 mm wide; the seat dip is ~60 mm up for a ~30 cm elf to straddle (or lie forward, rider-style).",
        "Print both halves flat as exported (inner face on the bed). They fit on one plate together (~274 × 185 mm).",
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
    "scale": 1.0,          # 1.0 ≈ 274 mm long (elf-sized); 0.5 makes a desk toy
    "half_width": 20.0,    # slab thickness of each half (bike width ≈ 2× this) at scale 1
    "roundover": 5.0,      # radius of the rounded outer edge at scale 1
    "line_height": 0.8,    # raised glow-stripe height (4 layers)
    "pin_d": 1.75,         # alignment pin = filament diameter
    "trail": True,         # also export the free-standing light-ribbon trail
    "trail_height": 40.0,
}

# Proportions follow the replica light cycles: big hubless wheels about
# 1.5 diameters apart, fender shells wrapped round the outside of each.
WHEEL_R = 36.0          # tyre outer radius
OPEN_R = 26.0           # hubless wheel: open centre, straight through the bike
BAND_IN, BAND_OUT = 27.5, 35.0   # raised glowing tyre band on the side face
REAR = (48.0, 38.0)
FRONT = (228.0, 38.0)
# Fender shells hug the outside of each wheel: a slightly larger circle pushed
# back (rear) / forward (front) and up, so the tyre peeks out underneath.
REAR_SHELL = ((REAR[0] - 6, REAR[1] + 6), WHEEL_R + 6)
FRONT_SHELL = ((FRONT[0] + 5, FRONT[1] + 5), WHEEL_R + 5)

# Spine between the wheels (x along the bike, front at +x; y up): high rear
# deck, deep seat dip, rising tank into the front shell, curved belly.
SPINE = [
    (40, 80), (70, 90), (100, 90), (116, 78), (128, 64), (142, 60), (162, 64),
    (184, 72), (204, 80), (226, 82), (238, 30), (206, 16), (176, 18),
    (150, 26), (120, 22), (90, 16), (62, 26),
]

PINS = [(REAR[0], 7.0), (FRONT[0], 7.0), (118, 45)]  # tyre bottoms + mid-spine


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


def _circ(center, r, s):
    return circle(2 * r * s).translate((center[0] * s, center[1] * s))


def _silhouette(s):
    parts = [polygon(_spline(SPINE) * s), _circ(REAR, WHEEL_R, s), _circ(FRONT, WHEEL_R, s),
             _circ(*REAR_SHELL, s), _circ(*FRONT_SHELL, s)]
    sil = _add(parts)
    sil = offset(offset(sil, 5 * s), -5 * s)   # fillet the shell/spine junctions
    sil = offset(offset(sil, -2 * s), 2 * s)   # and soften any sharp convex corners
    # Flat contact patch under each tyre so it stands steady.
    return sil - rect(400 * s, 4 * s).translate((150 * s, 0))


def _taper(points, widths, s):
    """Swoosh: a stroke whose width varies point to point (tapered ends)."""
    segs = []
    for (p0, w0), (p1, w1) in zip(zip(points, widths), zip(points[1:], widths[1:])):
        a = circle(w0 * s).translate((p0[0] * s, p0[1] * s))
        b = circle(w1 * s).translate((p1[0] * s, p1[1] * s))
        segs.append(CrossSection.batch_hull([a, b]))
    return _add(segs)


def _open_spline(pts, n=12):
    """Open Catmull-Rom spline through `pts` (ends held by repeating them)."""
    p = [pts[0]] + list(pts) + [pts[-1]]
    closed = _spline(p, n)  # closed curve through the padded list...
    return [tuple(q) for q in closed[n: n * (len(pts))]]  # ...keep the real span


def _arc(center, r, a0, a1, n=24):
    return [(center[0] + r * math.cos(math.radians(a)), center[1] + r * math.sin(math.radians(a)))
            for a in np.linspace(a0, a1, n)]


def _swooshes(s):
    # Rear: a crescent from the top of the rear fender down toward the seat.
    rear = _arc(REAR, 44, 90, 26)
    rear_w = np.interp(np.linspace(0, 1, len(rear)), [0, 0.25, 1], [2.4, 7.0, 1.6])
    # Front: runs forward along the tank, then sweeps down around the front tyre.
    front = _open_spline([(132, 51), (158, 54), (178, 53), (188, 42), (188, 30), (190, 24)])
    front_w = np.interp(np.linspace(0, 1, len(front)), [0, 0.3, 0.6, 1], [1.6, 4.0, 5.5, 1.6])
    return _add([_taper(rear, rear_w, s), _taper(front, front_w, s)])


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


def _half(s, half_width, roundover, line_height, pin_d):
    T, R = half_width * s, roundover * s
    sil = _silhouette(s)
    body = _rounded_slab(sil, T, R)  # round the outer outline only

    centres = [(REAR[0] * s, REAR[1] * s), (FRONT[0] * s, FRONT[1] * s)]
    cuts = []
    for c in centres:  # hubless wheels: open straight through
        cuts.append(hole(2 * OPEN_R * s, T, compensate=False).translate((c[0], c[1], 0)))
    # Engine vents: short engraved slots low on the spine.
    for y in (34, 39, 44):
        slot = stroke([(142 * s, y * s), (160 * s, (y + 1.5) * s)], 2.2 * s, segments=16)
        cuts.append(extrude_plain(slot, 1.2 * s + 0.02).translate((0, 0, T - 1.2 * s)))
    pin_depth = min(6.0, T - 3.0)
    for px, py in PINS:
        cuts.append(hole(pin_d + 2 * P.tol("snug"), pin_depth).translate((px * s, py * s, 0)))
    body = difference(body, cuts)

    # Glow: the tyre bands plus two swooshes, all on the flat top (clear of
    # the roundover and of the wheel openings).
    keep = offset(sil, -(R + 1.0 * s))
    for c in centres:
        keep = keep - circle(2 * (OPEN_R + 1.5) * s).translate(c)
    glow = _add([_ring(BAND_IN * s, BAND_OUT * s, c) for c in centres] + [_swooshes(s)])
    for c in centres:  # keep swooshes off the tyre bands, so the band edge stays crisp
        glow = glow - _ring((BAND_OUT + 0.01) * s, (BAND_OUT + 2.5) * s, c)
    glow = (glow ^ keep).simplify(1e-3)
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


def build(scale, half_width, roundover, line_height, pin_d, trail, trail_height):
    half = _half(scale, half_width, roundover, line_height, pin_d)
    parts = {"half-a": half, "half-b": on_bed(half.mirror((1, 0, 0)))}
    if trail:
        parts["trail"] = _trail(scale, trail_height)
    return parts
