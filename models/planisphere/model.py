"""Two-disc planisphere (star wheel) customised to one backyard.

Star disc (bottom): polar azimuthal-equidistant chart centred on the north
celestial pole, r = k * (90 - dec), stars to `mag_limit` as raised dots sized
by magnitude, constellation lines and names, and a date scale on the rim.

Mask (top): opaque, with a window cut to the *measured* horizon (site.yaml),
N/E/S/W labels, a faint engraved line for the ideal 0° horizon, a 24-hour
standard-time scale on the rim, and a site/DST plaque.

Pivot: M3 bolt + nut through a printed flanged sleeve (the repo's M3 hardware
helpers), sized so the discs turn freely with ~0.3 mm axial play.

Handedness — derived, not remembered
-----------------------------------
The wheel is read held up overhead / in front of you, printed face toward
you, with the direction you face at the bottom. Facing south, the south
horizon is at the bottom, the zenith above it, the pole above that and the
north horizon at the top; east is on your LEFT. So on the face (viewed from
+Z in model space) the mask maps hour angle HA (deg, + = west) to the polar
angle  theta_mask = -90 + HA:  S (HA 0) at the bottom, W (HA +90) right,
E (HA -90) left. A star's HA = LST - RA, so for fixed LST increasing RA is
decreasing HA = clockwise: the star disc uses  theta_disc = 90 - RA.
With the disc turned by rho (CCW), theta_disc + rho = theta_mask gives
rho = 15*LST - 180 (deg): the disc turns COUNTER-clockwise as LST grows, the
same sense as the sky turning about the pole as seen facing north.

Scales: a date mark sits at the disc angle of the RA on the meridian at the
local standard midnight ending that date, alpha(d) = 90 - LST_mid(d); the
time scale is beta(T) = -90 + 15*T (clock hours). Aligning date with time
sets rho = beta - alpha = 15*(T + LST_mid) - 180 = 15*LST - 180 (to within
the 0.27%% sidereal-rate difference: <= 2 min over +-12 h from midnight).
Later dates therefore run clockwise round the star disc and later times
counter-clockwise round the mask. Longitude vs the zone's central meridian is
inside LST_mid, so the time scale reads standard clock time directly.
"""

from __future__ import annotations

import csv
import math
from datetime import datetime, timedelta, timezone
from functools import cached_property
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import yaml
from manifold3d import CrossSection, JoinType, Manifold, OpType

from printlib.profile import load_printer
from printlib.shapes import METRIC, extrude, hole, nut_trap, pack, stroke, stroke_text

HERE = Path(__file__).parent
P = load_printer()
# "No stroke or gap narrower than two nozzle widths", and never below the
# profile's printable minimum wall.
MINW = max(2 * P.nozzle, float(P.design["min_wall"]))
CH = float(P.design["first_layer_chamfer"])
SEG = 12  # sides for small round features: <0.03 mm from a true circle at these sizes
STROKE = MINW + 0.1  # drawn lines/ticks: real margin over the minimum once polygonised

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

DEFAULT_CONSTELLATIONS = [
    "UMa", "UMi", "Cas", "Cep", "Dra", "Cyg", "Lyr", "Aql", "Her", "Boo",
    "Leo", "Vir", "Sco", "Sgr", "Ori", "Tau", "Gem", "Aur", "Per", "And", "Peg", "CMa",
]

META = {
    "title": "Backyard planisphere",
    "description": "Two-disc star wheel for one site, with a mask window cut to the measured horizon.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "color_change_z": 1.6,
    "notes": [
        "Three files: star disc, mask, pivot (flanged sleeve + washer). Hardware: one M3x8 socket-head bolt and one M3 nut.",
        "Single colour works (everything readable is raised 0.6 mm). For two colours, print dark and change to white/yellow "
        "at Z = 1.6 mm on the star disc and the mask (Anycubic Slicer Next: right-click the layer slider > Add colour change).",
        "Assembly: nut into the sleeve's flange from below, sleeve up through the star disc then the mask, washer on top, bolt down. "
        "Snug the bolt; the sleeve carries the clamp so the discs still turn.",
        "Polaris is within 0.6 deg of the pole, so it sits under the pivot hub.",
    ],
}

PARAMS = {
    "site_file": "site.yaml",
    "mag_limit": 4.5,
    "constellations": DEFAULT_CONSTELLATIONS,
    "star_disc_d": 264.0,   # fits the 310 mm usable bed with ~23 mm margin
    "mask_d": 224.0,
    "base_t": 1.6,          # disc thickness under the relief (= colour-change height)
    "relief": 0.6,          # raised features (3 layers)
    "chart_margin_deg": 4.0,
    "name_size": 4.0,       # constellation names (cap height)
}


# --------------------------------------------------------------------------- #
# astronomy (pure functions, also used by the tests)
# --------------------------------------------------------------------------- #
def gmst_deg(utc: datetime) -> float:
    """Greenwich mean sidereal time (IAU 1982), degrees."""
    jd = (utc - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400.0
    return (280.46061837 + 360.98564736629 * jd) % 360.0


def altaz_to_hadec(alt: np.ndarray, az: np.ndarray, lat: float):
    """(alt, az) deg, az from true north through east -> (HA deg, + west; dec deg)."""
    a, z, f = np.radians(alt), np.radians(az), math.radians(lat)
    sd = np.sin(f) * np.sin(a) + np.cos(f) * np.cos(a) * np.cos(z)
    dec = np.arcsin(np.clip(sd, -1, 1))
    y = -np.cos(a) * np.sin(z)
    x = np.sin(a) * np.cos(f) - np.cos(a) * np.cos(z) * np.sin(f)
    return np.degrees(np.arctan2(y, x)), np.degrees(dec)


def hadec_to_altaz(ha: np.ndarray, dec: np.ndarray, lat: float):
    h, d, f = np.radians(ha), np.radians(dec), math.radians(lat)
    sa = np.sin(f) * np.sin(d) + np.cos(f) * np.cos(d) * np.cos(h)
    alt = np.arcsin(np.clip(sa, -1, 1))
    y = -np.cos(d) * np.sin(h)
    x = np.sin(d) * np.cos(f) - np.cos(d) * np.cos(h) * np.sin(f)
    return np.degrees(alt), np.degrees(np.arctan2(y, x)) % 360.0


class Wheel:
    """All geometry for one site. Angles in degrees, lengths in mm."""

    def __init__(self, site_file="site.yaml", mag_limit=4.5, constellations=DEFAULT_CONSTELLATIONS,
                 star_disc_d=264.0, mask_d=224.0, base_t=1.6, relief=0.6, chart_margin_deg=4.0, name_size=4.0):
        path = Path(site_file)
        cfg = yaml.safe_load((path if path.is_absolute() else HERE / path).read_text())
        s = cfg["site"]
        self.name = s["name"]
        self.lat, self.lon = float(s["latitude_deg"]), float(s["longitude_deg"])
        if self.lat < 10:
            raise ValueError("This chart is centred on the north celestial pole; it needs a northern site (lat >= 10).")
        self.tz = ZoneInfo(s["timezone"])
        jan = datetime(2026, 1, 15, tzinfo=self.tz).utcoffset()
        jul = datetime(2026, 7, 15, tzinfo=self.tz).utcoffset()
        self.std_offset_h = min(jan, jul).total_seconds() / 3600.0
        self.central_meridian = 15.0 * self.std_offset_h
        hz = cfg["horizon"]
        self.declination = float(hz["magnetic_declination_deg"])
        samples = sorted((float(k), float(v)) for k, v in hz["altitude_by_azimuth"].items())
        self._horizon_samples = samples

        self.mag_limit, self.constellations = mag_limit, list(constellations)
        self.R_star, self.R_mask = star_disc_d / 2, mask_d / 2
        self.base_t, self.relief, self.name_size = base_t, relief, name_size
        if self.R_star > min(P.usable_volume[:2]) / 2 - 5:
            raise ValueError("star disc doesn't fit the bed with margin")
        # Radial layout: time ring on the mask's outer 12 mm, then room for the
        # S label, then the deepest point of the window (south horizon).
        self.time_ring_in = self.R_mask - 12.0
        self.k = (self.time_ring_in - 8.0) / (180.0 - self.lat)  # mm per degree
        self.dec_min = -(90.0 - self.lat) - chart_margin_deg
        self.R_chart = self.k * (90.0 - self.dec_min)
        self.pivot_od = 6.0
        self.pivot_hole_d = self.pivot_od + 2 * P.tol("slide")
        self.hub_r = 8.0

    # --- projection ---------------------------------------------------------
    def r_of_dec(self, dec):
        return self.k * (90.0 - np.asarray(dec))

    def disc_xy(self, ra, dec):
        th, r = np.radians(90.0 - np.asarray(ra)), self.r_of_dec(dec)
        return np.stack([r * np.cos(th), r * np.sin(th)], axis=-1)

    def mask_xy(self, ha, dec):
        th, r = np.radians(-90.0 + np.asarray(ha)), self.r_of_dec(dec)
        return np.stack([r * np.cos(th), r * np.sin(th)], axis=-1)

    def mask_to_altaz(self, xy):
        xy = np.atleast_2d(xy)
        r, th = np.hypot(xy[:, 0], xy[:, 1]), np.degrees(np.arctan2(xy[:, 1], xy[:, 0]))
        return hadec_to_altaz(th + 90.0, 90.0 - r / self.k, self.lat)

    # --- time scales ----------------------------------------------------------
    def lst_deg(self, utc: datetime) -> float:
        return (gmst_deg(utc) + self.lon) % 360.0

    def date_angle(self, month: int, day: int) -> float:
        """Disc angle of the date mark: RA on the meridian at the standard-time
        midnight ending that date, averaged over a leap cycle."""
        vecs = []
        for year in (2025, 2026, 2027, 2028):
            local_mid = datetime(year, month, day) + timedelta(days=1)
            utc = (local_mid - timedelta(hours=self.std_offset_h)).replace(tzinfo=timezone.utc)
            a = math.radians(90.0 - self.lst_deg(utc))
            vecs.append((math.cos(a), math.sin(a)))
        c, s = np.mean(vecs, axis=0)
        return math.degrees(math.atan2(s, c))

    @staticmethod
    def time_angle(hours: float) -> float:
        """Mask angle of a standard clock time (hours, 0-24)."""
        return -90.0 + 15.0 * hours

    def disc_rotation(self, month: int, day: int, hours: float) -> float:
        """CCW rotation of the star disc when `day` is set against `hours`."""
        return self.time_angle(hours) - self.date_angle(month, day)

    # --- horizon ---------------------------------------------------------------
    def obstruction(self, az_true):
        """Obstruction altitude at TRUE azimuth.

        Samples are magnetic; shift by the declination, then interpolate with a
        monotone cubic (PCHIP) wrapped around 360 deg. Smooth (C1) but, unlike a
        cubic spline, never overshoots: a treeline doesn't grow phantom bumps.
        """
        from scipy.interpolate import PchipInterpolator

        mag = np.array([a for a, _ in self._horizon_samples])
        alt = np.array([h for _, h in self._horizon_samples])
        true = (mag + self.declination) % 360.0
        order = np.argsort(true)
        x, y = true[order], alt[order]
        pad = min(3, len(x))
        xs = np.concatenate([x[-pad:] - 360.0, x, x[:pad] + 360.0])
        ys = np.concatenate([y[-pad:], y, y[:pad]])
        q = np.asarray(az_true, dtype=float) % 360.0
        return np.clip(PchipInterpolator(xs, ys)(q), 0.0, 89.0)

    def horizon_xy(self, alt_fn, n=720):
        az = np.linspace(0, 360, n, endpoint=False)
        ha, dec = altaz_to_hadec(alt_fn(az), az, self.lat)
        return self.mask_xy(ha, dec)

    @cached_property
    def window(self) -> CrossSection:
        return CrossSection([self.horizon_xy(self.obstruction)]).simplify(1e-3)

    def in_window(self, xy) -> bool:
        from shapely.geometry import Point, Polygon

        return Polygon(self.horizon_xy(self.obstruction)).contains(Point(*xy))

    # --- catalog -----------------------------------------------------------------
    @cached_property
    def stars(self) -> dict[str, dict]:
        rows = {}
        with open(HERE / "data" / "stars.csv") as f:
            for r in csv.DictReader(f):
                key = r["hip"] or f"x{len(rows)}"
                rows[key] = dict(ra=float(r["ra_deg"]), dec=float(r["dec_deg"]), mag=float(r["mag"]), name=r["name"], con=r["con"])
        return rows

    @cached_property
    def lines(self) -> dict[str, list[tuple[str, str]]]:
        out: dict[str, list] = {}
        with open(HERE / "data" / "constellation_lines.csv") as f:
            for r in csv.DictReader(f):
                out.setdefault(r["con"], []).append((r["hip1"], r["hip2"]))
        return out

    @cached_property
    def latin(self) -> dict[str, str]:
        with open(HERE / "data" / "constellations.csv") as f:
            return {r["con"]: r["latin"] for r in csv.DictReader(f)}

    def chart_stars(self):
        return [s for s in self.stars.values() if s["mag"] <= self.mag_limit and s["dec"] >= self.dec_min]

    @staticmethod
    def dot_d(mag: float) -> float:
        for limit, d in ((0.5, 3.4), (1.5, 2.8), (2.5, 2.2), (3.5, 1.6)):
            if mag <= limit:
                return d
        return 1.2

    # --- 2D layers (star disc, disc coordinates) ----------------------------
    def _dots(self):
        cs = [CrossSection.circle(self.dot_d(s["mag"]) / 2, SEG).translate(tuple(self.disc_xy(s["ra"], s["dec"])))
              for s in self.chart_stars()]
        return CrossSection.batch_boolean(cs, OpType.Add)

    def _lines(self):
        pieces = []
        for con in self.constellations:
            for a, b in self.lines.get(con, []):
                sa, sb = self.stars[a], self.stars[b]
                if min(sa["dec"], sb["dec"]) < self.dec_min:
                    continue
                pts = _great_circle(sa["ra"], sa["dec"], sb["ra"], sb["dec"])
                xy = self.disc_xy(pts[:, 0], pts[:, 1])
                # Leave a clear gap (>= MINW) around each star dot.
                trim_a = (self.dot_d(sa["mag"]) if sa["mag"] <= self.mag_limit else 0) / 2 + MINW + 0.3
                trim_b = (self.dot_d(sb["mag"]) if sb["mag"] <= self.mag_limit else 0) / 2 + MINW + 0.3
                xy = _trim_polyline(xy, trim_a, trim_b)
                if xy is not None:
                    pieces.append(stroke(xy, STROKE, 10))
        return CrossSection.batch_boolean(pieces, OpType.Add) if pieces else CrossSection()

    def _names(self, faint: CrossSection, bright: CrossSection):
        """Place each constellation name near its stars, avoiding bright stars
        (never covered), other names, and as much faint detail as possible."""
        labels = []
        keep_bright = _grow(bright, MINW + 0.3)
        keep_faint = _grow(faint, MINW + 0.2)
        for con in self.constellations:
            hips = {h for seg in self.lines.get(con, []) for h in seg}
            pts = np.array([self.disc_xy(self.stars[h]["ra"], self.stars[h]["dec"]) for h in hips
                            if self.stars[h]["dec"] >= self.dec_min])
            if len(pts) == 0:
                continue
            c = pts.mean(axis=0)
            name = self.latin.get(con, con).upper()
            placed = _grow(CrossSection.batch_boolean(labels, OpType.Add), MINW + 0.6) if labels else None
            best = None
            for dist in (0.0, 3.0, 6.0, 9.0, 12.0):  # stay close: a far label misleads
                for ang in (range(0, 360, 30) if dist else [0]):
                    p = c + dist * np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))])
                    rp = float(np.hypot(*p))
                    if rp > self.R_chart - 5 or rp < self.hub_r + 8:
                        continue
                    t = self._label(name, self.name_size, p)
                    score = (t ^ keep_faint).area() + 40 * (t ^ keep_bright).area() \
                        + (40 * (t ^ placed).area() if placed else 0.0) + 0.6 * dist
                    if best is None or score < best[0]:
                        best = (score, t)
                if best and best[0] < 1.0:
                    break
            if best:
                labels.append(best[1])
        return CrossSection.batch_boolean(labels, OpType.Add) if labels else CrossSection()

    @staticmethod
    def _label(text: str, size: float, at, up_to_centre: bool = True) -> CrossSection:
        """Text centred at `at`, rotated so its top points at the pivot — upright
        when that part of the wheel is at the bottom (where you're facing)."""
        t = _text(text, size)
        if up_to_centre:
            t = t.rotate(math.degrees(math.atan2(at[1], at[0])) + 90.0)
        return t.translate(tuple(at))

    def _date_ring(self):
        r0 = self.R_mask + 1.2
        parts = []
        for m in range(12):
            for d in range(1, MONTH_DAYS[m] + 1):
                length = 5.5 if d == 1 else 3.5 if d % 5 == 0 else 2.0
                parts.append(_radial_tick(self.date_angle(m + 1, d), r0, r0 + length, STROKE))
                if d in (10, 20):
                    parts.append(self._label(str(d), 4.0, _polar(self.date_angle(m + 1, d), r0 + 3.5 + 3.6)))
            mid = _circ_mean(self.date_angle(m + 1, 1), self.date_angle(m + 1, MONTH_DAYS[m]))
            parts.append(self._label(MONTHS[m], 5.0, _polar(mid, self.R_star - 5.2)))
        return CrossSection.batch_boolean(parts, OpType.Add)

    def star_relief(self) -> CrossSection:
        stars = self.chart_stars()
        bright = CrossSection.batch_boolean(
            [CrossSection.circle(self.dot_d(s["mag"]) / 2, SEG).translate(tuple(self.disc_xy(s["ra"], s["dec"])))
             for s in stars if s["mag"] <= 3.0], OpType.Add)
        dots, lines = self._dots(), self._lines()
        faint = (dots - bright) + lines
        names = self._names(faint, bright)
        # Faint stars and line segments give way under names; bright stars never do.
        chart = (faint - _grow(names, MINW + 0.1)) + bright + names
        chart = chart ^ CrossSection.circle(self.R_chart, 360)
        chart = chart - CrossSection.circle(self.pivot_hole_d / 2 + 1.5, 96)
        # Cutting faint detail back around names (and clipping at the chart edge
        # and pivot) leaves slivers; drop anything thinner than MINW first.
        return _close_gaps(_drop_thin(chart) + self._date_ring())

    # --- 2D layers (mask, observer coordinates) ------------------------------------
    def mask_window(self) -> CrossSection:
        win = self.window
        if win.area() and _contains(win, (0.0, 0.0)):
            # Pole is visible: keep a hub for the pivot, joined by a bar along the
            # northern meridian to the nearest window edge.
            top = self.horizon_xy(self.obstruction)
            north = max(top, key=lambda p: p[1] if abs(p[0]) < 1.0 else -1e9)
            bar = CrossSection.square((2.4, north[1] + 2.0)).translate((-1.2, 0.0))
            win = win - CrossSection.circle(self.hub_r, 96) - bar
        return win

    def mask_relief(self) -> CrossSection:
        R = self.R_mask
        parts = []
        for q in range(96):  # quarter-hour ticks to the rim
            h = q / 4
            length = 4.0 if q % 4 == 0 else 2.6 if q % 2 == 0 else 1.6
            parts.append(_radial_tick(self.time_angle(h), R - 0.4 - length, R - 0.4, STROKE))
            if q % 4 == 0:
                parts.append(self._label(str(int(h)), 4.4, _polar(self.time_angle(h), R - 0.4 - 4.0 - 1.4 - 2.2)))
        # Compass labels just outside the window edge at true N/E/S/W.
        zen = self.mask_xy(*altaz_to_hadec(np.array([90.0]), np.array([0.0]), self.lat))[0]
        for az, letter in ((0, "N"), (90, "E"), (180, "S"), (270, "W")):
            ha, dec = altaz_to_hadec(self.obstruction(np.array([az])), np.array([float(az)]), self.lat)
            p = self.mask_xy(ha, dec)[0]
            u = (p - zen) / np.linalg.norm(p - zen)
            parts.append(self._label(letter, 5.0, p + u * 4.6))
        relief = CrossSection.batch_boolean(parts, OpType.Add) + self._plaque()
        return _close_gaps(_drop_thin(relief - _grow(self.mask_window(), MINW)))

    def _plaque_lines(self):
        lat = f"{abs(self.lat):.2f}{'N' if self.lat >= 0 else 'S'}"
        lon = f"{abs(self.lon):.2f}{'E' if self.lon >= 0 else 'W'}"
        off = int(self.std_offset_h) if self.std_offset_h == int(self.std_offset_h) else self.std_offset_h
        return [self.name.upper(), f"{lat} {lon}", f"STANDARD TIME UTC{off:+}", "ADD 1 HOUR DURING", "DAYLIGHT SAVING"]

    def _plaque(self) -> CrossSection:
        """Raised plate with the site + DST note engraved through it (dark text
        on light in two colours, crisp engraving in one)."""
        lines = self._plaque_lines()
        size, pitch = 4.0, 6.8
        n_top = self.horizon_xy(self.obstruction)[:, 1].max()
        y0 = n_top + 17.0 + (len(lines) - 1) * pitch
        text = CrossSection.batch_boolean(
            [_text(t, size).translate((0, y0 - i * pitch)) for i, t in enumerate(lines)], OpType.Add)
        x0, y_lo, x1, y_hi = text.bounds()
        plate = _rounded_rect(x1 - x0 + 7, y_hi - y_lo + 7, 2.0).translate(((x0 + x1) / 2, (y_lo + y_hi) / 2))
        return plate - text

    def ideal_horizon_groove(self) -> CrossSection:
        """Faint engraved 0 deg horizon, where it runs over opaque mask."""
        pts = self.horizon_xy(lambda az: np.zeros_like(az))
        groove = stroke(np.vstack([pts, pts[:1]]), STROKE)
        return groove - _grow(self.mask_window(), 1.2)

    # --- 3D parts ------------------------------------------------------------------
    def star_disc(self) -> Manifold:
        base = extrude(CrossSection.circle(self.R_star, 360), self.base_t, bottom_chamfer=CH)
        top = Manifold.extrude(self.star_relief(), self.relief + 0.01).translate((0, 0, self.base_t - 0.01))
        return (base + top) - hole(self.pivot_hole_d, self.base_t + 1, compensate=False)

    def mask(self) -> Manifold:
        plate = CrossSection.circle(self.R_mask, 360) - self.mask_window()
        base = extrude(plate, self.base_t, bottom_chamfer=CH)
        top = Manifold.extrude(self.mask_relief(), self.relief + 0.01).translate((0, 0, self.base_t - 0.01))
        groove = Manifold.extrude(self.ideal_horizon_groove(), 1.0).translate((0, 0, self.base_t - 0.4))
        return ((base + top) - groove) - hole(self.pivot_hole_d, self.base_t + 1, compensate=False)

    def pivot(self) -> Manifold:
        """Flanged sleeve (nut trapped in the flange) + top washer, for one M3 bolt."""
        stack = self.base_t + self.relief + self.base_t  # star disc + relief gap + mask
        sleeve_len = stack + 0.3                          # axial play: turns freely, no flop
        flange_t, washer_t, od = 3.0, 1.6, 14.0
        clear = METRIC["M3"]["clearance"]
        sleeve = extrude(CrossSection.circle(od / 2, 64), flange_t, bottom_chamfer=CH)
        sleeve = sleeve + Manifold.cylinder(sleeve_len + 0.01, self.pivot_od / 2, circular_segments=48).translate((0, 0, flange_t - 0.01))
        sleeve = sleeve - hole(clear, flange_t + sleeve_len, compensate=False) - nut_trap("M3", depth=2.6)
        washer = extrude(CrossSection.circle(od / 2, 64) - CrossSection.circle(clear / 2 + 0.1, 32), washer_t, bottom_chamfer=CH)
        return pack([sleeve, washer], width=60, gap=6)


# --------------------------------------------------------------------------- #
# 2D helpers
# --------------------------------------------------------------------------- #
def _polar(angle_deg: float, r: float):
    a = math.radians(angle_deg)
    return (r * math.cos(a), r * math.sin(a))


def _circ_mean(a: float, b: float) -> float:
    return math.degrees(math.atan2(math.sin(math.radians(a)) + math.sin(math.radians(b)),
                                   math.cos(math.radians(a)) + math.cos(math.radians(b))))


def _radial_tick(angle_deg: float, r0: float, r1: float, w: float) -> CrossSection:
    t = CrossSection.square((r1 - r0, w)).translate((r0, -w / 2))
    return t.rotate(angle_deg)


def _rounded_rect(w: float, h: float, r: float) -> CrossSection:
    return CrossSection.square((w - 2 * r, h - 2 * r), center=True).offset(r, JoinType.Round, circular_segments=32)


def _trim_polyline(xy: np.ndarray, d0: float, d1: float):
    """Cut d0 mm off the start and d1 mm off the end of a polyline."""
    seglen = np.hypot(*np.diff(xy, axis=0).T)
    total = seglen.sum()
    if total <= d0 + d1 + MINW:
        return None
    cum = np.concatenate([[0], np.cumsum(seglen)])
    s = np.linspace(d0, total - d1, max(2, len(xy)))
    return np.stack([np.interp(s, cum, xy[:, 0]), np.interp(s, cum, xy[:, 1])], axis=-1)


def _great_circle(ra0, dec0, ra1, dec1, step_deg=1.0) -> np.ndarray:
    def vec(ra, dec):
        ra, dec = math.radians(ra), math.radians(dec)
        return np.array([math.cos(dec) * math.cos(ra), math.cos(dec) * math.sin(ra), math.sin(dec)])

    a, b = vec(ra0, dec0), vec(ra1, dec1)
    ang = math.acos(max(-1.0, min(1.0, float(a @ b))))
    n = max(2, int(math.degrees(ang) / step_deg) + 1)
    out = []
    for t in np.linspace(0, 1, n):
        if ang < 1e-9:
            v = a
        else:
            v = (math.sin((1 - t) * ang) * a + math.sin(t * ang) * b) / math.sin(ang)
        out.append((math.degrees(math.atan2(v[1], v[0])) % 360, math.degrees(math.asin(max(-1, min(1, v[2]))))))
    return np.array(out)


def _text(text: str, cap: float) -> CrossSection:
    """Single-stroke text: every stroke and letter gap is exactly MINW+ wide."""
    return stroke_text(text, cap, width=STROKE, gap=MINW + 0.15, segments=10)


def _grow(cs: CrossSection, d: float) -> CrossSection:
    return cs.offset(d, JoinType.Round, circular_segments=SEG).simplify(1e-3)


def _drop_thin(cs: CrossSection, w: float = MINW) -> CrossSection:
    """Morphological opening: remove any sliver narrower than w (it couldn't print)."""
    return cs.offset(-w / 2, JoinType.Round, circular_segments=SEG).offset(w / 2, JoinType.Round, circular_segments=SEG).simplify(1e-3)


def _close_gaps(cs: CrossSection, w: float = MINW) -> CrossSection:
    """Morphological closing: fill any gap narrower than w (it couldn't print)."""
    return cs.offset(w / 2, JoinType.Round, circular_segments=SEG).offset(-w / 2, JoinType.Round, circular_segments=SEG).simplify(1e-3)


def _contains(cs: CrossSection, pt) -> bool:
    return (cs ^ CrossSection.circle(0.01, 8).translate(pt)).area() > 0


# --------------------------------------------------------------------------- #
def build(site_file, mag_limit, constellations, star_disc_d, mask_d, base_t, relief, chart_margin_deg, name_size):
    w = Wheel(site_file, mag_limit, constellations, star_disc_d, mask_d, base_t, relief, chart_margin_deg, name_size)
    return {"star-disc": w.star_disc(), "mask": w.mask(), "pivot": w.pivot()}


def wheel(**overrides) -> Wheel:
    return Wheel(**{**PARAMS, **overrides})


# --------------------------------------------------------------------------- #
# 2D preview
# --------------------------------------------------------------------------- #
def _patch(cs: CrossSection, rotate_deg: float = 0.0, **kw):
    from matplotlib.patches import PathPatch
    from matplotlib.path import Path as MPath

    verts, codes = [], []
    for poly in cs.rotate(rotate_deg).to_polygons():
        poly = np.asarray(poly)
        verts += list(poly) + [poly[0]]
        codes += [MPath.MOVETO] + [MPath.LINETO] * (len(poly) - 1) + [MPath.CLOSEPOLY]
    return PathPatch(MPath(verts, codes), **kw)


def render_overlay(w: Wheel, month: int, day: int, hours: float, out: str | Path, star_names=()) -> Path:
    """Star disc, mask, and the two overlaid at a date/time (standard clock time)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    rho = w.disc_rotation(month, day, hours)
    disc_base = CrossSection.circle(w.R_star, 360) - CrossSection.circle(w.pivot_hole_d / 2, 64)
    star_rel = w.star_relief()
    mask_plate = CrossSection.circle(w.R_mask, 360) - w.mask_window() - CrossSection.circle(w.pivot_hole_d / 2, 64)
    mask_rel, groove = w.mask_relief(), w.ideal_horizon_groove()
    navy, light, dark = "#18233f", "#f3eccc", "#2b2b2b"

    fig, axes = plt.subplots(1, 3, figsize=(24, 8.6), dpi=110)
    titles = ["Star disc (bottom)", "Mask (top)",
              f"Set for {MONTHS[month - 1].title()} {day}, {int(hours):02d}:{int(round(hours % 1 * 60)):02d} standard time"]
    for i, ax in enumerate(axes):
        if i in (0, 2):
            r = rho if i == 2 else 0.0
            ax.add_patch(_patch(disc_base, r, facecolor=navy, edgecolor="none"))
            ax.add_patch(_patch(star_rel, r, facecolor=light, edgecolor="none"))
        if i in (1, 2):
            ax.add_patch(_patch(mask_plate, facecolor=dark, edgecolor="none", alpha=0.93 if i == 2 else 1.0))
            ax.add_patch(_patch(mask_rel, facecolor="#e0e0e0", edgecolor="none"))
            if groove.area():
                ax.add_patch(_patch(groove, facecolor="#555555", edgecolor="none"))
        if i == 2 and star_names:
            a = math.radians(rho)
            for name in star_names:
                s = next(v for v in w.stars.values() if v["name"] == name)
                x, y = w.disc_xy(s["ra"], s["dec"])
                x, y = x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)
                if _contains(w.mask_window(), (x, y)):
                    ax.annotate(name, (x, y), xytext=(4, 4), textcoords="offset points", color="#ffb347", fontsize=9)
        lim = w.R_star + 4
        ax.set_xlim(-lim, lim)
        ax.set_ylim(-lim, lim)
        ax.set_aspect("equal")
        ax.set_facecolor("white")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_title(titles[i], fontsize=14)
    fig.suptitle(f"{w.name} planisphere — printed face, held facing south (S at bottom, E on the left)", fontsize=15)
    fig.tight_layout()
    out = Path(out)
    fig.savefig(out)
    plt.close(fig)
    return out


if __name__ == "__main__":
    import sys

    args = sys.argv[1:] or ["2026-12-15", "22:00"]
    d = datetime.strptime(args[0], "%Y-%m-%d")
    hh, mm = map(int, args[1].split(":"))
    path = render_overlay(wheel(), d.month, d.day, hh + mm / 60, HERE / "preview-overlay.png",
                          star_names=("Sirius", "Betelgeuse", "Rigel", "Aldebaran", "Capella", "Deneb", "Vega", "Altair", "Fomalhaut"))
    print(f"wrote {path}")
