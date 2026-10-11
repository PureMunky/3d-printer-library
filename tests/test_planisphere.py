"""Check the planisphere against an independent ephemeris (astropy).

For three dates/times and a dozen bright stars: set the wheel the way a
person would (the date on the star disc against the clock time on the mask),
find where each star lands in the mask frame, and compare with the true
altitude/azimuth. Catches a mirrored chart, a reversed date or time scale,
a wrong longitude/time-zone correction and a misplaced window.
"""

import math
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pytest

astropy = pytest.importorskip("astropy")
import astropy.units as u  # noqa: E402
from astropy.coordinates import AltAz, EarthLocation, SkyCoord  # noqa: E402
from astropy.time import Time  # noqa: E402
from astropy.utils import iers  # noqa: E402

from printlib.build import load_model  # noqa: E402

iers.conf.auto_download = False
warnings.simplefilter("ignore")

MODEL = load_model(Path(__file__).resolve().parent.parent / "models" / "planisphere")

# Textbook J2000 positions (h m s, d m s) — independent of the model's catalog.
STARS = {
    "Sirius": ("06 45 08.9", "-16 42 58"),
    "Vega": ("18 36 56.3", "+38 47 01"),
    "Arcturus": ("14 15 39.7", "+19 10 57"),
    "Capella": ("05 16 41.4", "+45 59 53"),
    "Rigel": ("05 14 32.3", "-08 12 06"),
    "Betelgeuse": ("05 55 10.3", "+07 24 25"),
    "Altair": ("19 50 47.0", "+08 52 06"),
    "Deneb": ("20 41 25.9", "+45 16 49"),
    "Aldebaran": ("04 35 55.2", "+16 30 33"),
    "Spica": ("13 25 11.6", "-11 09 41"),
    "Antares": ("16 29 24.5", "-26 25 55"),
    "Regulus": ("10 08 22.3", "+11 58 02"),
    "Fomalhaut": ("22 57 39.0", "-29 37 20"),
}

# Local STANDARD clock times (the wheel's time scale), evenings so the date
# on the wheel is simply the calendar date.
WHEN = [(2026, 12, 15, 22.0), (2027, 4, 10, 21.5), (2027, 8, 5, 23.0)]

HORIZON_MARGIN = 2.5  # deg: skip stars this close to the horizon either side
POSITION_TOL = 1.5    # deg: date/time scale granularity + epoch drift


@pytest.fixture(scope="module")
def wheel():
    return MODEL.wheel()


def _truth(w, name, when):
    y, mo, d, h = when
    local = datetime(y, mo, d) + timedelta(hours=h)
    utc = (local - timedelta(hours=w.std_offset_h)).replace(tzinfo=timezone.utc)
    ra, dec = STARS[name]
    c = SkyCoord(ra, dec, unit=(u.hourangle, u.deg), frame="icrs")
    loc = EarthLocation(lat=w.lat * u.deg, lon=w.lon * u.deg, height=300 * u.m)
    aa = c.transform_to(AltAz(obstime=Time(utc), location=loc, pressure=0))
    return float(aa.alt.deg), float(aa.az.deg)


def _model_position(w, name, when):
    """Where the star sits in the mask frame with the wheel set to `when`."""
    _, mo, d, h = when
    star = next(s for s in w.stars.values() if s["name"] == name)
    xy = w.disc_xy(star["ra"], star["dec"])
    rho = math.radians(w.disc_rotation(mo, d, h))
    rot = np.array([[math.cos(rho), -math.sin(rho)], [math.sin(rho), math.cos(rho)]])
    return rot @ xy


def _sep(alt1, az1, alt2, az2):
    a1, a2, d = map(math.radians, (alt1, alt2, az1 - az2))
    c = math.sin(a1) * math.sin(a2) + math.cos(a1) * math.cos(a2) * math.cos(d)
    return math.degrees(math.acos(max(-1, min(1, c))))


def test_catalog_matches_reference(wheel):
    for name, (ra, dec) in STARS.items():
        star = next(s for s in wheel.stars.values() if s["name"] == name)
        ref = SkyCoord(ra, dec, unit=(u.hourangle, u.deg))
        got = SkyCoord(star["ra"] * u.deg, star["dec"] * u.deg)
        assert ref.separation(got).deg < 0.6, name  # J2030 precession is ~0.4 deg


def test_handedness_is_the_overhead_view(wheel):
    """Seen from the printed face (+Z) with S at the bottom, E must be LEFT."""
    for az, check in ((180, lambda p: p[1] < 0), (90, lambda p: p[0] < 0), (270, lambda p: p[0] > 0)):
        from_model = wheel.mask_xy(*MODEL.altaz_to_hadec(np.array([0.0]), np.array([float(az)]), wheel.lat))[0]
        assert check(from_model), az
    # Later dates run clockwise on the disc; later times counter-clockwise on the mask.
    d1, d2 = wheel.date_angle(3, 1), wheel.date_angle(3, 2)
    assert ((d2 - d1 + 180) % 360) - 180 < 0
    assert ((wheel.time_angle(21) - wheel.time_angle(20) + 180) % 360) - 180 > 0


@pytest.mark.parametrize("when", WHEN, ids=lambda w: f"{w[0]}-{w[1]:02d}-{w[2]:02d}T{w[3]:05.2f}")
def test_stars_match_sky(wheel, when):
    window = wheel.mask_window()
    checked_up = checked_down = 0
    for name in STARS:
        alt, az = _truth(wheel, name, when)
        horizon = float(wheel.obstruction(np.array([az]))[0])
        p = _model_position(wheel, name, when)
        inside = MODEL._contains(window, tuple(p))
        if alt > horizon + HORIZON_MARGIN:
            assert inside, f"{name} is up (alt {alt:.1f}, az {az:.1f}) but outside the window"
            m_alt, m_az = wheel.mask_to_altaz(p)
            sep = _sep(alt, az, float(m_alt[0]), float(m_az[0]))
            assert sep < POSITION_TOL, f"{name}: wheel says alt {m_alt[0]:.1f} az {m_az[0]:.1f}, sky {alt:.1f} {az:.1f}"
            checked_up += 1
        elif alt < horizon - HORIZON_MARGIN:
            assert not inside, f"{name} is down (alt {alt:.1f}) but shows in the window"
            checked_down += 1
    assert checked_up >= 4 and checked_down >= 2, (checked_up, checked_down)


def test_clock_correction_is_baked_in(wheel):
    """Longitude is 7.7 deg west of the zone meridian: the same sky comes ~31 min
    later by the clock than at the meridian, and the scales must encode that."""
    assert wheel.central_meridian == -75.0
    lag_min = (wheel.central_meridian - wheel.lon) * 4
    assert lag_min == pytest.approx(30.7, abs=0.2)
    # Moving the site to the zone meridian must shift the date scale by that lag.
    shifted = MODEL.Wheel.__new__(MODEL.Wheel)
    shifted.__dict__.update(wheel.__dict__)
    shifted.lon = wheel.central_meridian
    delta = (wheel.date_angle(6, 1) - shifted.date_angle(6, 1)) % 360
    assert delta == pytest.approx(lag_min / 4, abs=0.05)


def test_window_follows_measured_horizon_and_declination(tmp_path):
    """A 25 deg obstruction measured at MAGNETIC 187.46 must sit at TRUE 180."""
    import yaml

    site = yaml.safe_load((MODEL.HERE / "site.yaml").read_text())
    samples = {a: 0.0 for a in range(0, 360, 15)}
    for a in samples:
        true = (a + site["horizon"]["magnetic_declination_deg"]) % 360
        samples[a] = 25.0 if abs(((true - 180 + 180) % 360) - 180) < 30 else 0.0
    site["horizon"]["altitude_by_azimuth"] = samples
    path = tmp_path / "site.yaml"
    path.write_text(yaml.safe_dump(site))
    w = MODEL.wheel(site_file=str(path))

    assert w.obstruction(np.array([180.0]))[0] == pytest.approx(25.0, abs=1.0)
    assert w.obstruction(np.array([0.0]))[0] == pytest.approx(0.0, abs=1.0)
    win = w.mask_window()

    def at(alt, az):
        ha, dec = MODEL.altaz_to_hadec(np.array([alt]), np.array([az]), w.lat)
        return tuple(w.mask_xy(ha, dec)[0])

    assert not MODEL._contains(win, at(15.0, 180.0))  # behind the obstruction
    assert MODEL._contains(win, at(35.0, 180.0))      # above it
    assert MODEL._contains(win, at(5.0, 30.0))         # open sky to the NNE (off the hub bar)
    # The ideal-horizon groove now has opaque mask to run over in the south.
    assert w.ideal_horizon_groove().area() > 10


@pytest.fixture(scope="module")
def reliefs(wheel):
    return {"star disc": wheel.star_relief(), "mask": wheel.mask_relief(), "mask plaque": wheel._plaque()}


@pytest.mark.parametrize("layer", ["star disc", "mask", "mask plaque"])
def test_no_stroke_or_gap_below_two_nozzle_widths(reliefs, layer):
    """Opening by MINW removes nothing real (no thin strokes); closing adds
    nothing real (no thin gaps). Slivers at sharp corners (<0.1 mm) ignored."""
    from manifold3d import JoinType

    cs, w = reliefs[layer], MODEL.MINW

    def morph(a, d1, d2):
        return a.offset(d1, JoinType.Round, circular_segments=24).offset(d2, JoinType.Round, circular_segments=24)

    thin = (cs - morph(cs, -w / 2 + 0.01, w / 2 - 0.01)).offset(-0.1, JoinType.Round, circular_segments=24).area()
    gaps = (morph(cs, w / 2 - 0.01, -w / 2 + 0.01) - cs).offset(-0.1, JoinType.Round, circular_segments=24).area()
    assert thin < 0.002 * cs.area(), f"{layer}: {thin:.2f} mm² of strokes thinner than {w} mm"
    assert gaps < 0.002 * cs.area(), f"{layer}: {gaps:.2f} mm² of gaps narrower than {w} mm"
