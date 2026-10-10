"""1:6-scale household accessories for Barbie-size (~29 cm) dolls, plus a
handful of little gummy bears — all packed onto one print plate.

Everything is sized from real objects divided by `scale` (6 = Barbie) and
shaped to print without supports: cups and pots are open-top, handles have
45° undersides, flat things (plates, phone, spoon, clock) lie flat, and the
gummy bears are domed silhouettes printed on their backs.
"""

import math

from manifold3d import CrossSection, Manifold

from printlib.profile import load_printer
from printlib.shapes import (
    LAYER,
    box,
    circle,
    cylinder,

    extrude,
    hole,
    label_face,
    offset,

    pack,
    polygon,
    rect,
    union,
)

P = load_printer()
CH = P.design["first_layer_chamfer"]

META = {
    "title": "Doll household accessories + gummy bears",
    "description": "One plate of 1:6-scale kitchen and home accessories for Barbie-size dolls, plus 8 gummy bears.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Household set: 2 mugs, 2 plates, 2 bowls, frying pan, pot + lid, toaster, open laptop, phone, "
        "TV remote, 3 books, cutting board, spoon, spatula, wall clock, trash can.",
        "Everything prints in one go, no supports. Use a brim only if your first layer is fussy — the parts are small.",
        "Set split=true to get the household items and the gummy bears as separate files (e.g. to print the bears in "
        "translucent coloured PLA/PETG so they look like real gummies).",
        "The gummy bears look edible but are plastic and small — keep them away from little kids.",
        "Engraved details (phone screen, laptop keys, book pages) pop if you wipe on a little acrylic paint.",
    ],
}

PARAMS = {
    "scale": 6.0,          # real size / scale; 6 ≈ Barbie (1:6)
    "gummy_count": 8,
    "gummy_height": 10.0,  # mm; ~real gummy-bear size. 6 is still printable.
    "split": False,        # True: separate household + gummies STLs
    "plate_width": 250.0,
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _xz(profile: CrossSection, depth: float) -> Manifold:
    """Extrude a profile drawn in X/Z (as X/Y) through Y, centred on y=0."""
    return Manifold.extrude(profile, depth).rotate((90, 0, 0)).translate((0, depth / 2, 0))


def _cup(r, h, wall=1.2, floor=1.4, r_top=None):
    """Open-top round vessel (optionally flared); wall measured horizontally."""
    r_top = r if r_top is None else r_top
    outer = extrude_cone(r, r_top, h)
    slope = (r_top - r) / h
    inner = Manifold.cylinder(h - floor + 0.2, r - wall + slope * floor, r_top - wall + slope * 0.2)
    return outer - inner.translate((0, 0, floor))


def extrude_cone(r0, r1, h):
    """Frustum with the first-layer chamfer at the bottom edge."""
    body = Manifold.cylinder(h - CH, r0 + (r1 - r0) * CH / h, r1).translate((0, 0, CH))
    foot = Manifold.cylinder(CH, r0 - CH, r0 + (r1 - r0) * CH / h - 0.0)
    return body + foot


def _handle_loop(R, z0, reach, height, thick):
    """C-handle on the +X side of a vessel of radius R, 45° underside, open loop."""
    outer = polygon([(R - 0.6, z0), (R + reach, z0 + reach + 0.6), (R + reach, z0 + height), (R - 0.6, z0 + height)])
    hole_top = z0 + height - 1.6
    inner = polygon([(R + 0.4, z0 + 2.2), (R + reach - 1.6, z0 + reach + 0.6), (R + reach - 1.6, hole_top), (R + 0.4, hole_top)])
    return _xz(outer - inner, thick)


def _lug(R, z_top, reach, width, t=1.6):
    """Solid side lug (pot handle) with a 45° underside."""
    prof = polygon([(R - 0.6, z_top - t - reach - 0.6), (R + reach, z_top - t), (R + reach, z_top), (R - 0.6, z_top)])
    return _xz(prof, width)


# --------------------------------------------------------------------------- #
# household items (all sizes = real mm / s)
# --------------------------------------------------------------------------- #
def mug(s):
    R, H = 80 / s / 2, 95 / s
    body = extrude_cone(R, R, H)
    handle = _handle_loop(R, H * 0.18, 4.0, H * 0.72, 2.4)
    inner = Manifold.cylinder(H, R - 1.2).translate((0, 0, 1.6))
    return (body + handle) - inner


def dinner_plate(s):
    d = 270 / s
    base = extrude(circle(d), 1.2, bottom_chamfer=CH)
    rim = Manifold.extrude(circle(d - 0.6) - circle(d - 7), 0.8).translate((0, 0, 1.19))
    return base + rim


def bowl(s):
    r_top, h = 150 / s / 2, 60 / s
    r_bot = r_top * 0.55
    outer = extrude_cone(r_bot, r_top, h)
    k = (r_top - r_bot) / h
    wall, floor = 1.4, 1.4
    inner = Manifold.cylinder(h - floor + 0.2, r_bot + k * floor - wall, r_top + k * 0.2 - wall).translate((0, 0, floor))
    return outer - inner


def frying_pan(s):
    R, H = 240 / s / 2, 45 / s
    handle_len = 180 / s
    # The handle runs deep into the pan and the hollow is cut afterwards, so it
    # passes squarely through the wall (a rounded end grazing the curved wall
    # leaves micro-edges that tear the STL).
    handle = box(handle_len + R, 4.0, 2.4, r=1.5, bottom_chamfer=CH).translate(((handle_len + R) / 2, 0, 0))
    handle = handle - hole(2.0, 2.4).translate((R + handle_len - 3, 0, 0))
    inner = Manifold.cylinder(H, R - 1.2).translate((0, 0, 1.4))
    return (extrude_cone(R, R, H) + handle) - inner


def pot(s):
    R, H = 200 / s / 2, 140 / s
    body = _cup(R, H, wall=1.2, floor=1.4)
    lugs = _lug(R, H - 1.0, 3.0, 6.0)
    return body + lugs + lugs.mirror((1, 0, 0))


def pot_lid(s):
    R = 200 / s / 2 + 0.6
    lid = extrude(circle(2 * R), 1.2, bottom_chamfer=CH)
    knob = cylinder(5.0, 2.4).translate((0, 0, 1.19))
    return lid + knob


def toaster(s):
    W, D, H = 280 / s, 170 / s, 190 / s
    t = box(W, D, H, r=3.5, bottom_chamfer=CH)
    slot = box(W * 0.68, 3.2, H, r=1.0)
    for y in (-D * 0.2, D * 0.2):
        t = t - slot.translate((0, y, H * 0.4))
    lever = _xz(polygon([(W / 2 - 0.4, H * 0.55 - 2.6), (W / 2 + 2.2, H * 0.55), (W / 2 + 2.2, H * 0.55 + 1.6), (W / 2 - 0.4, H * 0.55 + 1.6)]), 4.0)
    return t + lever


def laptop(s):
    W, D = 330 / s, 220 / s
    base = box(W, D, 2.4, r=1.0, bottom_chamfer=CH)
    base = label_face(base, rect(W - 8, D * 0.45, r=0.5), "+z", depth=0.4, offset=(0, D * 0.12))
    for i in range(1, 4):  # key rows
        base = label_face(base, rect(W - 10, 0.5), "+z", depth=0.8, offset=(0, D * 0.12 - D * 0.225 + i * D * 0.1125))
    base = label_face(base, rect(W * 0.28, D * 0.22, r=0.6), "+z", depth=0.4, offset=(0, -D * 0.3))
    screen_h = 200 / s
    screen = box(W, screen_h, 1.8, r=1.0).translate((0, screen_h / 2, 0))
    screen = screen - box(W - 4, screen_h - 4, 1).translate((0, screen_h / 2, 1.4))
    # Lid stands upright: on a tilted lid every edge of the display recess
    # slices into one-layer slivers; upright, they're plain horizontal ledges.
    screen = screen.rotate((90, 0, 0)).translate((0, D / 2 - 0.9, 1.9))
    return base + screen


def phone(s):
    p = box(150 / s, 75 / s, 1.6, r=1.6, bottom_chamfer=CH)
    p = label_face(p, rect(150 / s - 3.0, 75 / s - 2.4, r=1.0), "+z", depth=0.4)
    return p


def tv_remote(s):
    L, W = 180 / s, 50 / s
    r = box(L, W, 2.8, r=2.0, bottom_chamfer=CH)
    buttons = [circle(1.8).translate((L / 2 - 3, 0))]
    for i in range(3):
        for j in (-1, 0, 1):
            buttons.append(circle(1.3).translate((L / 2 - 8 - i * 3.2, j * 2.4)))
    return r + Manifold.extrude(CrossSection.batch_boolean(buttons, _add()), 0.5).translate((0, 0, 2.79))


def _add():
    from manifold3d import OpType

    return OpType.Add


def book(s, w=240, d=160, t=30):
    L, W, T = w / s, d / s, t / s
    b = box(L, W, T, r=0.4, bottom_chamfer=CH)
    cover = 0.8
    band = 0.6
    cut_outer = box(L + 4, W + 4, T - 2 * cover).translate((0, 0, cover))
    keep = box(L + 4, W - 2 * band, T - 2 * cover + 1).translate((-band - 2, 0, cover - 0.5))
    pages = b - (cut_outer - keep)
    for z in (cover + 0.6, cover + 1.4, T - cover - 0.6):  # page-edge lines on the fore edge
        if z < T - cover - 0.2:
            pages = pages - box(0.6, W - 2 * band - 1.2, 0.3).translate((L / 2 - band - 0.25, 0, z))
    return pages


def cutting_board(s):
    L, W = 300 / s, 200 / s
    board = box(L, W, 2.0, r=2.5, bottom_chamfer=CH)
    tab = box(9, 9, 2.0, r=3.5, bottom_chamfer=CH).translate((L / 2 + 2.5, 0, 0))
    return (board + tab) - hole(3.0, 2.0).translate((L / 2 + 3.5, 0, 0))


def spoon(s):
    L = 180 / s
    head = CrossSection.circle(3.0).scale((1.45, 1.0)).translate((L / 2 - 4.3, 0))
    shaft = rect(L - 7, 2.2, r=1.0).translate((-3.5, 0))
    return extrude(head + shaft, 1.2, bottom_chamfer=0.2)


def spatula(s):
    L = 280 / s
    blade = rect(11, 10, r=1.2).translate((L / 2 - 5.5, 0))
    for y in (-2.6, 0, 2.6):
        blade = blade - rect(6.5, 1.1, r=0.5).translate((L / 2 - 5, y))
    shaft = rect(L - 10, 2.4, r=1.0).translate((-5, 0))
    return extrude(blade + shaft, 1.2, bottom_chamfer=0.2)


def wall_clock(s):
    d = 300 / s
    face = extrude(circle(d), 1.6, bottom_chamfer=CH)
    raised = circle(d - 0.6) - circle(d - 3.6)
    for i in range(12):
        a = math.radians(i * 30)
        tick = rect(1.2, 3.0 if i % 3 == 0 else 2.0).rotate(-i * 30)
        raised = raised + tick.translate((math.sin(a) * (d / 2 - 4.5), math.cos(a) * (d / 2 - 4.5)))
    raised = raised + rect(1.4, d * 0.24).translate((0, d * 0.12))                # hour hand
    raised = raised + rect(1.2, d * 0.36).translate((0, d * 0.18)).rotate(-110)  # minute hand
    raised = raised + circle(3.0)
    return face + Manifold.extrude(raised, 0.8).translate((0, 0, 1.59))


def trash_can(s):
    R, H = 260 / s / 2, 400 / s
    can = _cup(R, H, wall=1.2, floor=1.4)
    pedal = _xz(polygon([(-R + 0.6, 0), (-R - 3.0, 0), (-R - 3.0, 1.4), (-R + 0.6, 3.0)]), 6.0).rotate((0, 0, 90))
    return can + pedal.translate((0, 0, 0))


# --------------------------------------------------------------------------- #
# gummy bears
# --------------------------------------------------------------------------- #
def _bear_outline(height):
    parts = [
        CrossSection.circle(2.7).translate((0, 4.2)),                    # head
        CrossSection.circle(1.15).translate((-2.1, 6.4)),                # ears
        CrossSection.circle(1.15).translate((2.1, 6.4)),
        CrossSection.circle(3.2).scale((1.0, 1.2)).translate((0, -0.8)),  # body
        CrossSection.circle(1.3).translate((-3.3, 1.2)),                 # arms
        CrossSection.circle(1.3).translate((3.3, 1.2)),
        CrossSection.circle(1.6).translate((-2.2, -4.4)),                # legs
        CrossSection.circle(1.6).translate((2.2, -4.4)),
    ]
    cs = CrossSection.batch_boolean(parts, _add())
    k = height / 13.6  # outline is ~13.6 units tall
    return offset(cs.scale((k, k)), 0.0)


def gummy_bear(height):
    """Domed bear silhouette printed on its back: rounded top, flat bottom."""
    cs = _bear_outline(height)
    h = height * 0.42
    dome = min(h * 0.75, height * 0.22)
    steps = max(2, round(dome / LAYER))
    slabs = [extrude(cs, h - dome + 0.01, bottom_chamfer=0.2)]
    for i in range(steps):  # quarter-circle profile, one slab per layer
        z0 = h - dome + i * dome / steps
        inset = dome * (1 - math.sqrt(max(0.0, 1 - ((i + 1) / steps) ** 2)))
        layer = offset(cs, -inset)
        if not layer.is_empty():
            slabs.append(Manifold.extrude(layer, dome / steps + 0.01).translate((0, 0, z0)))
    return union(slabs)


# --------------------------------------------------------------------------- #
def build(scale, gummy_count, gummy_height, split, plate_width):
    s = scale
    household = [
        laptop(s), toaster(s), dinner_plate(s), dinner_plate(s), frying_pan(s), wall_clock(s),
        cutting_board(s), pot(s), pot_lid(s), trash_can(s),
        book(s), book(s, 220, 150, 25), book(s, 200, 135, 20),
        bowl(s), bowl(s), mug(s), mug(s), tv_remote(s), phone(s), spatula(s), spoon(s),
    ]
    gummies = [gummy_bear(gummy_height) for _ in range(gummy_count)]
    if split:
        return {"household": pack(household, plate_width), "gummies": pack(gummies, plate_width)}
    return pack(household + gummies, plate_width)



