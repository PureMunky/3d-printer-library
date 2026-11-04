"""Elf-scale light cycle — a sleek, glowing-striped sci-fi motorbike sized for
a ~30 cm shelf elf (or any similar plush/figure) to ride.

Construction (print-friendly by design):
  * The bike is two mirrored side halves, each a flat slab printed lying on
    its inner face. Every detail (wheel grooves, recessed rims, hub) is on the
    top face, so there are no overhangs and no supports.
  * The "light" stripes and wheel rings are raised 0.8 mm above the slab top.
    Add a filament change at the slab-top height (see notes) and they print in
    a second colour: black body, cyan/orange glow lines — no painting.
  * The halves line up with 1.75 mm filament offcuts as alignment pins, then
    glue (CA or PLA-safe glue) face to face.
  * Optional `trail`: a free-standing L-shaped "light wall" to set behind the
    bike for a scene. Print it in translucent / glow PLA.
"""

from manifold3d import CrossSection

from printlib.profile import load_printer
from printlib.shapes import (
    circle,
    difference,
    extrude,
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
    "description": "Sci-fi light cycle sized for a 30 cm shelf elf, two glue-together halves with two-colour glow stripes, plus an optional light-wall trail.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Default size ≈ 266 mm long × 104 mm tall × 46 mm wide, seat dip ~79 mm up — about right for a ~30 cm elf to straddle the seat dip.",
        "Print both halves flat as exported (inner face on the bed). They fit on one plate together (~266 × 220 mm).",
        "Two-colour stripes: add a filament change / pause at the slab top (Z = half_width, 22.0 mm by default). "
        "In Anycubic Slicer Next: preview slider → right-click the first layer above 22.0 mm → Add color change (M600) or Add pause. "
        "Start in black, swap to cyan (classic) or orange (villain) PLA.",
        "Assembly: cut 3 pieces of 1.75 mm filament ~11 mm long, push them into the pin holes of one half, "
        "press the other half on, then glue. Superglue (CA) or a thin layer of PLA-safe glue.",
        "Trail wall: print in translucent or glow-in-the-dark PLA; it stands on its own behind the bike.",
        "Each half is a large flat slab; a brim isn't needed on PEI, but clean the bed so the long tail and nose don't lift.",
    ],
}

PARAMS = {
    "scale": 1.0,          # 1.0 ≈ 265 mm long (elf-sized); 0.5 makes a desk toy
    "half_width": 22.0,    # slab thickness of each half (bike width ≈ 2× this) at scale 1
    "line_height": 0.8,    # raised glow-stripe height (4 layers)
    "line_width": 2.4,     # glow-stripe width at scale 1
    "pin_d": 1.75,         # alignment pin = filament diameter
    "trail": True,         # also export the free-standing light-wall trail
    "trail_height": 45.0,
}

WHEEL_R = 48.0
REAR = (52.0, 48.0)
FRONT = (210.0, 48.0)
# Wheel face detail radii. The groove must stay clear of the top chamfer where
# the wheel is flattened for its contact patch (46 mm from the hub minus 1.2).
GROOVE_R = 42.4
TYRE_R = 37.4
RIM_R = 35.4

# Hull silhouette in side view (x = along the bike, front at +x; y = up).
HULL = [
    (0, 62), (10, 90), (40, 104), (75, 103), (100, 92), (118, 80), (150, 79),
    (172, 90), (198, 106), (226, 106), (252, 92), (266, 66), (262, 40),
    (240, 22), (160, 14), (100, 14), (30, 22), (4, 40),
]

# Glow-stripe paths (scale 1), inset from the silhouette.
TOP_STRIPE = [(9, 64), (18, 87), (42, 97.5), (74, 97), (97, 86), (116, 73.5),
              (151, 73), (174, 84), (199, 99.5), (225, 99.5), (246, 88), (258, 66)]
BELLY_STRIPE = [(104, 21), (156, 21)]

PINS = [(52, 48), (210, 48), (131, 46)]  # on wheel hubs + mid-body


def _silhouette(s):
    wheel = circle(2 * WHEEL_R * s)
    parts = [polygon([(x * s, y * s) for x, y in HULL]),
             wheel.translate((REAR[0] * s, REAR[1] * s)),
             wheel.translate((FRONT[0] * s, FRONT[1] * s))]
    sil = CrossSection.batch_boolean(parts, _add())
    # Flat contact patch under each wheel so it stands steady.
    return sil - rect(400 * s, 4 * s).translate((150 * s, 0))


def _add():
    from manifold3d import OpType

    return OpType.Add


def _ring(r_in, r_out, center):
    return (circle(2 * r_out) - circle(2 * r_in)).translate(center)


def _half(s, half_width, line_height, line_width, pin_d):
    T = half_width * s
    sil = _silhouette(s)
    slab = extrude(sil, T, bottom_chamfer=P.design["first_layer_chamfer"], top_chamfer=1.2 * s)

    centres = [(REAR[0] * s, REAR[1] * s), (FRONT[0] * s, FRONT[1] * s)]
    groove_w, groove_d = 1.4 * s, 1.0 * s
    recess_d = 1.2 * s

    cuts = []
    for c in centres:
        # Thin groove separating the wheel disc from the body.
        g = _ring(GROOVE_R * s, GROOVE_R * s + groove_w, c)
        cuts.append(extrude(g, groove_d + 0.02).translate((0, 0, T - groove_d)))
        # Recessed rim area between hub and tyre ring.
        r = _ring(16.0 * s, RIM_R * s, c)
        cuts.append(extrude(r, recess_d + 0.02).translate((0, 0, T - recess_d)))
    # Alignment pin holes from the inner (bed) face.
    pin_depth = min(6.0, T - 3.0)
    for px, py in PINS:
        cuts.append(hole(pin_d + 2 * P.tol("snug"), pin_depth).translate((px * s, py * s, 0)))
    body = difference(slab, cuts)

    # Raised glow lines on the top face.
    lw = line_width * s
    paths = [TOP_STRIPE, BELLY_STRIPE]
    lines = [stroke([(x * s, y * s) for x, y in p], lw, segments=20) for p in paths]
    for c in centres:
        lines.append(_ring(TYRE_R * s, TYRE_R * s + lw, c))   # tyre ring, just outside the rim recess
        lines.append(_ring(11.0 * s, 11.0 * s + lw, c))   # hub ring
    glow = CrossSection.batch_boolean(lines, _add())
    # Keep stripes off the wheel grooves and well inside the chamfered edge.
    keep = offset(sil, -2.5 * s)
    for c in centres:
        keep = keep - _ring((GROOVE_R - 0.6) * s, GROOVE_R * s + groove_w + 0.6 * s, c)
        keep = keep - _ring(15.4 * s, (RIM_R + 0.6) * s, c)  # and off the rim recess
    glow = (glow ^ keep).simplify(1e-3)
    sink = 0.3  # sink stripes into the slab so the union is solid
    body = body + extrude(glow, sink + line_height).translate((0, 0, T - sink))
    return on_bed(body)


def _trail(s, h):
    t = 3.2
    a, b = 140.0 * s, 70.0 * s
    h = h * s
    pts = [(0, 0), (a, 0), (a, b)]
    wall = extrude(stroke(pts, t, segments=16), h, bottom_chamfer=P.design["first_layer_chamfer"])
    foot = extrude(stroke(pts, 12.0, segments=24), 2.0, bottom_chamfer=P.design["first_layer_chamfer"])
    return on_bed(union(wall, foot))


def build(scale, half_width, line_height, line_width, pin_d, trail, trail_height):
    half = _half(scale, half_width, line_height, line_width, pin_d)
    parts = {"half-a": half, "half-b": on_bed(half.mirror((1, 0, 0)))}
    if trail:
        parts["trail"] = _trail(scale, trail_height)
    return parts
