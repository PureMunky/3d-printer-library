"""Hitchhiker ghosts: an original trio of little sheet ghosts thumbing a
ride, sized to stand beside (or ride along with) a ~30 cm shelf elf.

  * drifter: tall and wavy, one thumb up, the other arm hanging loose
  * puddles: short and round, holding up a little "RIDE?" sign
  * wisp:    tiny, thumb up, with a suitcase at its side

Print-friendly by design, upright with no supports:
  * Bodies are bell shapes (revolved profile) that only narrow going up, with
    a domed head. The wavy hem is a radial warp that fades out with height.
  * Every limb and blob is built as a hull with a 45° "keel" underneath, so
    no underside is flatter than 45°.
  * Eyes are upward-pointing teardrops and mouths are diamonds, so the
    pockets have 45° roofs instead of flat ceilings.
  * The sign is a pennant shape with 45° lower edges.
"""

import math

import numpy as np
from manifold3d import CrossSection, Manifold

from printlib.profile import load_printer
from printlib.shapes import on_bed, polygon, text2d, union

P = load_printer()

META = {
    "title": "Hitchhiker ghosts",
    "description": "Original trio of little sheet ghosts thumbing a ride (tall, round with a sign, tiny with a suitcase), elf-scale, support-free.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Sizes at scale 1: drifter ~120 mm tall, puddles ~88 mm, wisp ~66 mm — they fit in the ghost buggy beside an elf.",
        "Print upright as exported, no supports. All three fit on one plate.",
        "Glow-in-the-dark or white/translucent PLA. A black paint pen (or acrylic wash) in the eyes, mouth and sign letters makes the faces pop.",
        "Glow PLA is abrasive: fine for a one-off on the stock brass nozzle, but use a hardened nozzle if you print a lot of it.",
        "Checker WARN (puddles, ~16 mm² at the sign): the flat tops of the 0.8 mm-deep engraved letters on the vertical sign. "
        "They're sub-millimetre bridges and print cleanly without support; accepted.",
        "Thumbs and the sign stick are the most delicate bits; 3 walls (and 0.12–0.16 mm layers if you like) keep them crisp.",
    ],
}

PARAMS = {
    "scale": 1.0,       # 1.0 = elf scale; 0.6 makes desk/dollhouse-sized ghosts
    "sign_text": "RIDE?",
    "eye_depth": 3.0,
}


# --------------------------------------------------------------------------- #
# Building blocks
# --------------------------------------------------------------------------- #
def _blob(c, r):
    """Sphere with a 45° cone 'keel' beneath it: no flat-ish underside."""
    c = np.asarray(c, float)
    s = Manifold.sphere(r, 32).translate(tuple(c))
    tip = Manifold.sphere(0.05, 8).translate(tuple(c - (0, 0, r * math.sqrt(2))))
    return Manifold.batch_hull([s, tip])


def _limb(pts, radii):
    """Tapered limb through points: union of keeled hulls between joints."""
    segs = []
    for (a, ra), (b, rb) in zip(zip(pts, radii), zip(pts[1:], radii[1:])):
        segs.append(Manifold.batch_hull([_blob(a, ra), _blob(b, rb)]))
    return union(segs)


def _thumbs_up(c, r, side, s):
    """Hitchhiker's fist: an upright fist with four curled-finger knuckles
    stacked down its front and a short, stout thumb jutting sideways off the
    top at 45° (away from the body, slightly back), so the gesture reads as
    a thumb, not a pointing finger. `side` is +1 for a right hand (+X)."""
    cx, cy, cz = c
    fist = Manifold.batch_hull([_blob((cx, cy, cz - 0.45 * r), 0.85 * r), _blob((cx, cy, cz + 0.4 * r), 0.85 * r)])
    knuckles = [_blob((cx - side * 0.1 * r, cy - 0.7 * r, cz - 0.62 * r + i * 0.38 * r), 0.3 * r) for i in range(4)]
    base = (cx + side * 0.3 * r, cy + 0.1 * r, cz + 0.55 * r)
    tip = (base[0] + side * 5.0 * s, base[1] + 1.0 * s, base[2] + 5.0 * s)
    thumb = _limb([base, tip], [2.8 * s, 2.4 * s])
    return union(fist, thumb, *knuckles)


def _body(height, r_base, r_head, waves=7, wave_amp=0.09, lean=0.0):
    """Bell-shaped sheet ghost: hem radius r_base tapering to a domed head.
    Only narrows going up, so it never overhangs. Optional sideways lean."""
    zh = height - r_head                      # head centre height
    pts = [(0.0, 0.0)]
    for t in np.linspace(0, 1, 40):
        z = zh * t
        r = r_head + (r_base - r_head) * (1 - t) ** 1.7
        pts.append((r, z))
    for a in np.linspace(0, 90, 24)[1:]:
        pts.append((r_head * math.cos(math.radians(a)), zh + r_head * math.sin(math.radians(a))))
    pts.append((0.0, height))
    body = Manifold.revolve(CrossSection([np.array(pts)]), 96)

    def warp(v):
        x, y, z = v[:, 0], v[:, 1], v[:, 2]
        th = np.arctan2(y, x)
        fade = np.clip(1 - z / (0.35 * height), 0, 1) ** 1.5
        k = 1 + wave_amp * np.sin(waves * th) * fade
        out = v.copy()
        out[:, 0] = x * k + lean * z ** 2 / height
        out[:, 1] = y * k
        return out

    return body.warp_batch(warp)


def _face(ghost, head_c, r_head, s, eye_depth, look=0.0):
    """Teardrop eyes + diamond mouth pocketed into the front (-Y) of the head."""
    def drop(w):
        r = w / 2
        return CrossSection.circle(r, 32) + polygon([(-r / math.sqrt(2), r / math.sqrt(2)), (0, r * math.sqrt(2)),
                                                       (r / math.sqrt(2), r / math.sqrt(2)), (0, 0)])
    eye_w, eye_dx, eye_dz = 0.30 * r_head, 0.36 * r_head, 0.12 * r_head
    feats = [drop(eye_w).scale((1, 1.25)).translate((-eye_dx + look, eye_dz)),
             drop(eye_w).scale((1, 1.25)).translate((eye_dx + look, eye_dz)),
             polygon([(0, -0.38), (0.13, -0.25), (0, -0.12), (-0.13, -0.25)]).scale((r_head, r_head)).translate((look, -0.1 * r_head))]
    cs = CrossSection.batch_boolean(feats, _add_op())
    hx, hy, hz = head_c
    # Extrude along local +Z, turn so local +Y is up and the extrusion runs
    # along -Y, then slide it to start in front of the face and run inward.
    reach = r_head + 2
    tool = Manifold.extrude(cs, reach).rotate((90, 0, 0)).translate((hx, hy - r_head - 2 + reach, hz))
    # Keep only a shell `eye_depth` deep behind the head surface.
    shell = Manifold.sphere(r_head + 2, 64).translate(head_c) - Manifold.sphere(r_head - eye_depth, 64).translate(head_c)
    return ghost - (tool ^ shell)


def _add_op():
    from manifold3d import OpType

    return OpType.Add


def _head_centre(height, r_head, lean=0.0):
    zh = height - r_head
    return (lean * zh ** 2 / height, 0.0, zh)


# --------------------------------------------------------------------------- #
# The trio
# --------------------------------------------------------------------------- #
def _drifter(s, eye_depth):
    H, rb, rh = 120 * s, 34 * s, 19 * s
    body = _body(H, rb, rh, waves=7, wave_amp=0.10)
    hc = _head_centre(H, rh)
    # Raised right arm (+X), thumb up: shoulder -> elbow -> hand, rising ≥ 45°.
    sh = (14 * s, 0, 66 * s)
    arm = _limb([sh, (30 * s, -2 * s, 82 * s), (38 * s, -4 * s, 98 * s)], [7 * s, 5.5 * s, 5 * s])
    hand = _thumbs_up((38 * s, -4 * s, 99 * s), 6.5 * s, +1, s)
    # Left arm hangs loose, swinging slightly out.
    droop = _limb([(-14 * s, 0, 66 * s), (-26 * s, -2 * s, 46 * s)], [6.5 * s, 4.5 * s])
    ghost = union(body, arm, hand, droop)
    return on_bed(_face(ghost, hc, rh, s, eye_depth), center=False)


def _puddles(s, eye_depth, sign_text):
    H, rb, rh = 88 * s, 36 * s, 22 * s
    body = _body(H, rb, rh, waves=6, wave_amp=0.08)
    hc = _head_centre(H, rh)
    # Left arm (-X) holds the sign stick up.
    arm = _limb([(-16 * s, 0, 48 * s), (-30 * s, -6 * s, 62 * s), (-34 * s, -8 * s, 72 * s)], [7.5 * s, 6 * s, 5.5 * s])
    hand = _blob((-34 * s, -8 * s, 73 * s), 6 * s)
    stick = _limb([(-34 * s, -8 * s, 74 * s), (-34 * s, -8 * s, 100 * s)], [2.2 * s, 2.2 * s])
    # Pennant sign: flat top, 45° lower edges meeting the stick.
    w, top, plate_t = 46 * s, 128 * s, 4 * s
    half = w / 2
    outline = polygon([(-half, top - 22 * s), (-half, top), (half, top), (half, top - 22 * s), (0, top - 22 * s - half)])
    sign = Manifold.extrude(outline, plate_t).rotate((90, 0, 0)).translate((-34 * s, -8 * s + plate_t / 2, 0))
    label = text2d(sign_text, 7.5 * s).translate((0, top - 11 * s))
    letters = Manifold.extrude(label, 1.0 * s + 0.02).rotate((90, 0, 0)).translate((-34 * s, -8 * s - plate_t / 2 + 1.0 * s, 0))
    sign = sign - letters
    # Right arm: thumb out.
    arm2 = _limb([(16 * s, 0, 48 * s), (30 * s, -4 * s, 62 * s)], [7.5 * s, 5.5 * s])
    hand2 = _thumbs_up((31 * s, -4 * s, 63 * s), 6 * s, +1, s)
    ghost = union(body, arm, hand, stick, sign, arm2, hand2)
    return on_bed(_face(ghost, hc, rh, s, eye_depth, look=2 * s), center=False)


def _wisp(s, eye_depth):
    H, rb, rh = 66 * s, 22 * s, 14 * s
    body = _body(H, rb, rh, waves=5, wave_amp=0.10)
    hc = _head_centre(H, rh)
    arm = _limb([(10 * s, 0, 36 * s), (20 * s, -2 * s, 46 * s), (23 * s, -3 * s, 54 * s)], [5 * s, 4 * s, 3.8 * s])
    hand = _thumbs_up((23 * s, -3 * s, 55 * s), 4.8 * s, +1, 0.8 * s)
    # Suitcase standing beside it (merged into the hem so it's one part).
    cw, cd, ch = 22 * s, 10 * s, 17 * s
    case = Manifold.cube((cw, cd, ch)).translate((-rb - cw + 6 * s, -cd / 2, 0))
    # Handle: a 45°-roofed loop on top (pointed arch, prints without support).
    hx = -rb - cw / 2 + 6 * s
    loop = polygon([(-6 * s, 0), (-6 * s, 2 * s), (0, 7 * s), (6 * s, 2 * s), (6 * s, 0)])
    hole_ = polygon([(-3.5 * s, -0.1), (-3.5 * s, 1.5 * s), (0, 5 * s), (3.5 * s, 1.5 * s), (3.5 * s, -0.1)])
    handle = Manifold.extrude(loop - hole_, 3 * s).rotate((90, 0, 0)).translate((hx, 1.5 * s, ch - 0.01))
    band = Manifold.cube((cw + 0.8 * s, cd + 0.8 * s, 2 * s)).translate((-rb - cw + 5.6 * s, -cd / 2 - 0.4 * s, ch * 0.45))
    ghost = union(body, arm, hand, case, handle, band)
    return on_bed(_face(ghost, hc, rh, s, eye_depth * 0.8, look=-1 * s), center=False)


def build(scale, sign_text, eye_depth):
    return {
        "drifter": _drifter(scale, eye_depth),
        "puddles": _puddles(scale, eye_depth, sign_text),
        "wisp": _wisp(scale, eye_depth),
    }
