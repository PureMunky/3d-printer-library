"""Hitchhiker ghosts: an original trio of Victorian-era phantoms thumbing a
ride, sized to stand beside (or ride in the ghost buggy with) a ~30 cm shelf
elf. Full figures with faces and period clothes, trailing off into a wispy
tail that swirls down to a small round base.

  * conductor: ghostly railway conductor, peaked cap and buttoned coat,
               lantern held high, thumb out
  * widow:     tall lady in a mourning hat with a veil down her back, high
               collar and bustled skirt, leaning on a furled parasol, thumb out
  * newsboy:   small paperboy in a flat cap with a satchel of papers and a
               rolled newspaper, thumb out

Print-friendly by design, upright with no supports:
  * Bodies are revolved profiles (made elliptical for depth). Where they
    widen going down (skirt, coat) the slope stays well under 45°, and the
    tail tapers gently into a 45° fillet on the base.
  * Every limb, fist, head and blob is a hull with a 45° "keel" underneath.
  * Cap visors, the satchel and the lantern have 45° undersides; eyes are
    upward-pointing teardrops and mouths are diamonds (pointed roofs).
"""

import math

import numpy as np
from manifold3d import CrossSection, Manifold

from printlib.profile import load_printer
from printlib.shapes import on_bed, polygon, union

P = load_printer()

META = {
    "title": "Hitchhiker ghosts",
    "description": "Original trio of Victorian phantoms thumbing a ride (conductor with lantern, veiled widow with parasol, newsboy with satchel), elf-scale, support-free.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Heights at scale 1: conductor ~116 mm, widow ~119 mm, newsboy ~76 mm — they fit in the ghost buggy beside an elf.",
        "Print upright as exported, no supports. All three fit on one plate.",
        "Glow-in-the-dark, white or translucent PLA. A black paint pen (or acrylic wash) in the eyes and mouth makes the faces pop; "
        "a grey wash over the coat, dress and cap brings out the clothing.",
        "Glow PLA is abrasive: fine for a one-off on the stock brass nozzle, but use a hardened nozzle if you print a lot of it.",
        "Checker WARNs (small, accepted for now): ~6 mm² near the top of the conductor's lantern and ~12 mm² on the "
        "newsboy around face height. Both are tiny ledges that bridge fine unsupported; worth a look if those spots print rough.",
        "Thumbs, the parasol and the lantern hanger are the most delicate bits; 3 walls (and 0.12–0.16 mm layers if you like) keep them crisp.",
    ],
}

PARAMS = {
    "scale": 1.0,       # 1.0 = elf scale; 0.6 makes desk/dollhouse-sized ghosts
    "eye_depth": 2.5,
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


def _revolve(profile, s, depth=0.72, wisp=0.0, height=1.0):
    """Revolve an (r, z) profile, squash it front-to-back to `depth`, and
    optionally sway the tail sideways (`wisp`, fading out by mid-body)."""
    pts = np.array([(r * s, z * s) for r, z in profile])
    body = Manifold.revolve(CrossSection([pts]), 96)

    def warp(v):
        out = v.copy()
        out[:, 1] *= depth
        z = v[:, 2] / (height * s)
        out[:, 0] += wisp * s * np.sin(z * math.pi * 2.2) * np.clip(1 - z / 0.45, 0, 1)
        return out

    return body.warp_batch(warp)


def _head(c, r):
    """Head with a keeled jaw (the keel sinks into the neck)."""
    return _blob(c, r)


def _visor(head_c, r_head, z_top, reach, width, s):
    """Cap peak: a thin plate tilted down-and-forward at 45° from the cap
    band, like a real brim. Top and underside are both 45°, so it prints
    without support and stays clear of the eyes."""
    hx, hy, hz = head_c
    t = 1.3 * s
    y_in = hy - 0.75 * r_head                  # roots inside the head/cap
    y_edge = hy - r_head                       # head surface at the front
    tip_y = y_edge - reach
    drop = tip_y - y_in                        # negative: 45° means dz == dy
    side = polygon([(y_in, z_top), (tip_y, z_top + drop), (tip_y, z_top + drop - t), (y_in, z_top - t)])
    return _yz_prism(side, width).translate((hx, 0, 0))


def _yz_prism(cs_yz, width):
    """Extrude a profile drawn in (y, z) through `width` along X, centred."""
    m = Manifold.extrude(cs_yz, width)            # local (x=y_prof, y=z_prof, z=extrusion)
    m = m.rotate((90, 0, 0))                      # local y -> world z, extrusion -> world -y
    m = m.rotate((0, 0, 90))                      # local x (y_prof) -> world y, -y -> world +x
    return m.translate((-width / 2, 0, 0))


def _base(r, s):
    """Round display base with a chamfered bed edge."""
    disc = Manifold.cylinder(2.6 * s, r * s, r * s, 96).translate((0, 0, 0.4))
    foot = Manifold.cylinder(0.4 + 0.01, r * s - 0.4, r * s, 96)
    return disc + foot


def _face(ghost, head_c, r_head, s, eye_depth, look=0.0, eye_z=0.12):
    """Teardrop eyes + diamond mouth pocketed into the front (-Y) of the head."""
    def drop(w):
        r = w / 2
        return CrossSection.circle(r, 32) + polygon([(-r / math.sqrt(2), r / math.sqrt(2)), (0, r * math.sqrt(2)),
                                                       (r / math.sqrt(2), r / math.sqrt(2)), (0, 0)])
    eye_w, eye_dx, eye_dz = 0.30 * r_head, 0.36 * r_head, eye_z * r_head
    feats = [drop(eye_w).scale((1, 1.25)).translate((-eye_dx + look, eye_dz)),
             drop(eye_w).scale((1, 1.25)).translate((eye_dx + look, eye_dz)),
             polygon([(0, -0.38), (0.13, -0.25), (0, -0.12), (-0.13, -0.25)]).scale((r_head, r_head)).translate((look, (eye_z - 0.22) * r_head))]
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


def _buttons(zs, r_at, s, depth=0.72, r=1.5):
    return [_blob((0, -depth * r_at(z) * s + 0.5 * s, z * s), r * s) for z in zs]


# --------------------------------------------------------------------------- #
# The trio
# --------------------------------------------------------------------------- #
def _conductor(s, eye_depth):
    prof = [(0, 0), (6, 3), (5, 12), (5.5, 18), (7.5, 28), (10.5, 38), (13.5, 48), (15.5, 58),
            (16, 66), (15.5, 74), (14, 80), (11, 84), (5, 87), (4.5, 92), (0, 92)]
    body = _revolve(prof, s, wisp=2.5, height=116)
    hc, rh = (0, 0, 99 * s), 9.0 * s
    head = _head(hc, rh)
    # Peaked cap: crown flares out going up (fine), flat top, 45° visor.
    crown = Manifold.cylinder(9.5 * s, 7.8 * s, 9.6 * s, 64).translate((0, 0, 104 * s))
    band = Manifold.cylinder(2.0 * s, 8.4 * s, 8.4 * s, 64).translate((0, 0, 104.5 * s)) ^ Manifold.cylinder(30 * s, 20 * s).translate((0, 0, 104.5 * s))
    visor = _visor(hc, rh, 106.5 * s, 3.2 * s, 12 * s, s)
    # Coat: lapel buttons down the front.
    r_at = lambda z: np.interp(z, [p[1] for p in prof], [p[0] for p in prof])  # noqa: E731
    buttons = _buttons([56, 64, 72], r_at, s)
    # Right arm (+X): thumb out.
    arm = _limb([(12 * s, 0, 81 * s), (23 * s, -2 * s, 90 * s), (28 * s, -4 * s, 100 * s)], [5.5 * s, 4.5 * s, 4.2 * s])
    fist = _thumbs_up((28 * s, -4 * s, 101 * s), 5.5 * s, +1, s)
    # Left arm (-X) raised, lantern hanging below the hand.
    arm2 = _limb([(-12 * s, 0, 81 * s), (-23 * s, -3 * s, 92 * s), (-27 * s, -5 * s, 103 * s)], [5.5 * s, 4.5 * s, 4.2 * s])
    hand2 = Manifold.batch_hull([_blob((-27 * s, -5 * s, 102 * s), 4.6 * s), _blob((-27 * s, -5 * s, 105 * s), 4.2 * s)])
    lantern = _lantern((-33 * s, -5 * s, 97 * s), s)
    ghost = union(body, head, crown, band, visor, *buttons, arm, fist, arm2, hand2, lantern, _base(16, s))
    return on_bed(_face(ghost, hc, rh, s, eye_depth, eye_z=-0.12), center=False)


def _lantern(top, s):
    """Hand lantern hanging from a hook: hex body, pyramid roof, 45° pointed
    base, and a short hanger up to the hand."""
    tx, ty, tz = top
    r = 4.2 * s
    hexa = CrossSection.circle(r, 6)
    body = Manifold.extrude(hexa, 8 * s).translate((tx, ty, tz - 12 * s))
    roof = Manifold.cylinder(4 * s, r, 0.8 * s, 6).translate((tx, ty, tz - 4 * s))
    belly = Manifold.cylinder(r * 1.05, 0.4 * s, r, 6).translate((tx, ty, tz - 12 * s - r * 1.05))
    hanger = _limb([(tx, ty, tz - 0.5 * s), (tx + 3.5 * s, ty, tz + 4.5 * s), (tx + 6 * s, ty, tz + 6 * s)], [1.3 * s, 1.3 * s, 1.5 * s])
    return union(body, roof, belly, hanger)


def _widow(s, eye_depth):
    prof = [(0, 0), (6, 3), (4.5, 12), (6, 20), (10, 30), (14, 42), (16.5, 52), (14, 60),
            (9.5, 70), (10.5, 76), (11.5, 82), (11, 86), (5, 89), (5.2, 95), (0, 95)]
    body = _revolve(prof, s, wisp=-2.5, height=119)
    hc, rh = (0, 0, 103 * s), 8.5 * s
    head = _head(hc, rh)
    # Bustle: a soft bulge at the back of the skirt.
    bustle = _blob((0, 8 * s, 52 * s), 9 * s)
    # Mourning hat: small flat pillbox; veil drapes down her back.
    hat = Manifold.cylinder(5 * s, 6.5 * s, 7.2 * s, 64).translate((0, 1 * s, 109.5 * s))
    veil_full = Manifold.batch_hull([Manifold.cylinder(1.0, 6.6 * s, 6.6 * s, 48).translate((0, 2 * s, 111.5 * s)),
                                    Manifold.cylinder(1.0, 12.5 * s, 12.5 * s, 64).translate((0, 4 * s, 82 * s))])
    veil = veil_full ^ Manifold.cube((60 * s, 30 * s, 60 * s)).translate((-30 * s, 2.5 * s, 70 * s))
    # High collar.
    collar = Manifold.cylinder(5 * s, 5.4 * s, 6.2 * s, 48).translate((0, 0, 89 * s))
    # Left arm (-X): thumb out.
    arm = _limb([(-10 * s, 0, 84 * s), (-20 * s, -2 * s, 93 * s), (-25 * s, -4 * s, 103 * s)], [4.8 * s, 4 * s, 3.8 * s])
    fist = _thumbs_up((-25 * s, -4 * s, 104 * s), 5 * s, -1, s)
    # Right arm down to a furled parasol used as a cane.
    px, py = 20 * s, -4 * s
    arm2 = _limb([(10 * s, 0, 84 * s), (17 * s, -2 * s, 70 * s), (px, py, 60 * s)], [4.8 * s, 4 * s, 3.8 * s])
    hand2 = _blob((px, py, 60 * s), 4.2 * s)
    shaft = _limb([(px, py, 2 * s), (px, py, 92 * s)], [1.4 * s, 1.4 * s])
    furl = Manifold.batch_hull([Manifold.cylinder(1.0, 1.6 * s, 1.6 * s, 24).translate((px, py, 40 * s)),
                                Manifold.cylinder(1.0, 3.6 * s, 3.6 * s, 24).translate((px, py, 72 * s)),
                                Manifold.sphere(0.6 * s, 12).translate((px, py, 95 * s))])
    knob = _blob((px, py, 96 * s), 2.2 * s)
    base = Manifold.batch_hull([_base(16, s), _base(5, s).translate((px, py, 0))])
    ghost = union(body, head, bustle, hat, veil, collar, arm, fist, arm2, hand2, shaft, furl, knob, base)
    return on_bed(_face(ghost, hc, rh, s, eye_depth, look=-0.8 * s), center=False)


def _newsboy(s, eye_depth):
    prof = [(0, 0), (5, 3), (4, 10), (5, 16), (7.5, 24), (10, 32), (11.5, 40), (11.5, 48),
            (10.5, 53), (8, 56), (3.6, 58), (3.6, 61), (0, 61)]
    body = _revolve(prof, s, depth=0.75, wisp=2.0, height=76)
    hc, rh = (0, 0, 66.5 * s), 8.0 * s
    head = _head(hc, rh)
    # Flat cap: crown flares out going up, puffy dome top, 45° peak.
    cap = Manifold.revolve(CrossSection([np.array([(0, 0), (7.0, 0), (9.4, 2.6), (9.0, 4.2), (6, 5.6), (0, 6.2)]) * s]), 64)
    cap = cap.translate((0, 0.8 * s, 70 * s))
    visor = _visor(hc, rh, 72.0 * s, 3.0 * s, 11 * s, s)
    # Satchel on his left hip: 45° V-bottom so it prints without support,
    # plus a strap across the chest to the right shoulder.
    bag_side = polygon([(-5 * s, 0), (5 * s, 0), (5 * s, -7 * s), (0, -12 * s), (-5 * s, -7 * s)])
    bag = Manifold.extrude(bag_side, 6 * s).rotate((90, 0, 0)).translate((-12.5 * s, 3 * s, 40 * s))
    flap = Manifold.cube((10.6 * s, 0.8 * s, 4 * s)).translate((-17.8 * s, -3.6 * s, 36.4 * s))
    papers = Manifold.cube((7 * s, 3.5 * s, 3 * s)).translate((-16 * s, -1.75 * s, 39.5 * s))
    strap = _limb([(-11 * s, -6.5 * s, 41 * s), (0, -8.6 * s, 47 * s), (8.5 * s, -5 * s, 54 * s)], [1.4 * s, 1.4 * s, 1.4 * s])
    # Right arm: thumb out. Left arm: waving a rolled newspaper.
    arm = _limb([(9 * s, 0, 54 * s), (17 * s, -2 * s, 61 * s), (20 * s, -3 * s, 68 * s)], [4.2 * s, 3.6 * s, 3.4 * s])
    fist = _thumbs_up((20 * s, -3 * s, 69 * s), 4.4 * s, +1, 0.85 * s)
    arm2 = _limb([(-9 * s, 0, 54 * s), (-17 * s, -3 * s, 58 * s), (-21 * s, -5 * s, 64 * s)], [4.2 * s, 3.6 * s, 3.4 * s])
    hand2 = _blob((-21 * s, -5 * s, 64 * s), 3.8 * s)
    paper = _limb([(-18 * s, -5 * s, 60 * s), (-27 * s, -5 * s, 72 * s)], [2.6 * s, 2.6 * s])
    ghost = union(body, head, cap, visor, bag, flap, papers, strap, arm, fist, arm2, hand2, paper, _base(13, s))
    return on_bed(_face(ghost, hc, rh, s, eye_depth * 0.85, look=0.6 * s, eye_z=-0.12), center=False)


def build(scale, eye_depth):
    return {
        "conductor": _conductor(scale, eye_depth),
        "widow": _widow(scale, eye_depth),
        "newsboy": _newsboy(scale, eye_depth),
    }
