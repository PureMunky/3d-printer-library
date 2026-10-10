"""Claude desk buddy — a chunky, pixel-art critter in the style of the little
orange Claude Code mascot: blocky body, two tall eyes, stubby side arms and
four short legs.

Print-friendliness is baked into the shape:
  * Prints upright on its feet, no supports.
  * The arms' undersides are 45° chamfers instead of flat ledges.
  * Leg gaps are short bridges (well under max_bridge).
  * Eyes are pockets on the front face. Fill them with a paint pen, or print
    the `eyes` part in black and press the plugs in (snug fit from the profile).
"""

from manifold3d import Manifold

from printlib.profile import load_printer
from printlib.shapes import box, label_face, on_bed, polygon, rect, union

P = load_printer()

META = {
    "title": "Claude desk buddy",
    "description": "Blocky pixel-art Claude mascot figure for the desk, with optional press-in eye plugs.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [
        "Body: terracotta/orange PLA (Claude orange is roughly #D97757). Eyes: black PLA or a paint pen.",
        "Print the body upright on its feet as exported; no supports or brim needed.",
        "Eye plugs are tiny: print several copies, or add them to another black print's plate.",
        "Plugs use the `snug` fit; if they're loose, a drop of CA glue fixes it.",
    ],
}

PARAMS = {
    "scale": 1.0,        # 1.0 ≈ 56 mm wide x 36 mm tall; 2.0 is a chunky 11 cm buddy
    "depth": 22.0,       # front-to-back thickness at scale 1
    "eye_depth": 2.0,    # pocket depth (and plug height)
    "eye_plugs": True,   # also export press-in eye plugs as a separate part
}


def build(scale, depth, eye_depth, eye_plugs):
    s = scale
    D = depth * s
    leg_h, body_w, body_h = 8 * s, 44 * s, 28 * s
    top = leg_h + body_h

    body = box(body_w, D, body_h).translate((0, 0, leg_h))

    # Four stubby legs: two pairs, short gaps so the belly is an easy bridge.
    leg_w = 6 * s
    leg_xs = [-19 * s, -9 * s, 9 * s, 19 * s]
    legs = [box(leg_w, D, leg_h + 0.01, bottom_chamfer=P.design["first_layer_chamfer"]).translate((x, 0, 0)) for x in leg_xs]

    # At bigger scales the gaps between legs outgrow a clean bridge; fill the
    # top corners of any wide gap with 45° gussets so the span stays short.
    safe_span = P.design["max_bridge"] - 3
    for xl, xr in zip(leg_xs, leg_xs[1:]):
        a, b = xl + leg_w / 2, xr - leg_w / 2
        g = min(max(0.0, ((b - a) - safe_span) / 2), leg_h - 1)
        if g > 0:
            left = polygon([(a - 0.01, leg_h + 0.01), (a + g, leg_h + 0.01), (a - 0.01, leg_h - g)])
            right = polygon([(b + 0.01, leg_h + 0.01), (b + 0.01, leg_h - g), (b - g, leg_h + 0.01)])
            legs += [_through_y(left, D), _through_y(right, D)]

    # Arms: stubs on each side with a 45° chamfered underside (no ledge overhang).
    arm_out, arm_top, arm_bot = 5 * s, leg_h + 15 * s, leg_h + 9 * s
    x0 = body_w / 2 - 0.01
    profile = polygon([(x0, arm_bot - arm_out), (x0 + arm_out, arm_bot), (x0 + arm_out, arm_top), (x0, arm_top)])
    arm = _through_y(profile, D)
    arms = [arm, arm.mirror((1, 0, 0))]

    buddy = on_bed(union(body, legs, arms))

    # Eyes: tall rectangles in the upper body, pocketed into the front (-Y) face.
    eye_w, eye_h = 4 * s, 8 * s
    eye_x, eye_z = 12 * s, top - 10 * s
    face_mid_z = top / 2  # label_face offsets are from the face's bbox centre
    for x in (-eye_x, eye_x):
        buddy = label_face(buddy, rect(eye_w, eye_h), "-y", depth=eye_depth, offset=(x, eye_z - face_mid_z))

    if not eye_plugs:
        return buddy
    gap = P.tol("snug")
    plug = box(eye_w - 2 * gap, eye_h - 2 * gap, eye_depth)
    plugs = on_bed(plug.translate((-(eye_w + 3) / 2, 0, 0)) + plug.translate(((eye_w + 3) / 2, 0, 0)))
    return {"body": buddy, "eyes": plugs}


def _through_y(profile_xz, depth):
    """Extrude a profile drawn in X/Z (as X/Y) through the full Y depth, centred."""
    return Manifold.extrude(profile_xz, depth).rotate((90, 0, 0)).translate((0, depth / 2, 0))
