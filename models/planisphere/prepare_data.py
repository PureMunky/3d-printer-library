"""Download and reduce the open star + constellation data the planisphere uses.

Run once (or to refresh):  python models/planisphere/prepare_data.py

Sources (both CC BY-SA 4.0 — the derived CSVs in data/ are too):
  * HYG database v4.1, https://github.com/astronexus/HYG-Database
  * Stellarium "modern" sky culture constellation lines,
    https://github.com/Stellarium/stellarium/tree/master/skycultures/modern

Positions are precessed from J2000 to equinox J2030 (the middle of the
wheel's useful life), so the chart is within ~0.2° of date for 2020-2040.
"""

from __future__ import annotations

import csv
import io
import json
import urllib.request
from pathlib import Path

HERE = Path(__file__).parent
HYG_URL = "https://raw.githubusercontent.com/astronexus/HYG-Database/main/hyg/CURRENT/hygdata_v41.csv"
LINES_URL = "https://raw.githubusercontent.com/Stellarium/stellarium/master/skycultures/modern/index.json"
MAG_LIMIT = 5.0  # keep a little below the default chart limit so it can be raised later
EQUINOX = "J2030"


def _get(url: str, attempts: int = 6) -> bytes:
    """Download, resuming with HTTP Range if the connection drops mid-file."""
    import http.client
    import time

    data = b""
    for i in range(attempts):
        req = urllib.request.Request(url, headers={"Range": f"bytes={len(data)}-"} if data else {})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return data + r.read()
        except http.client.IncompleteRead as e:
            data += e.partial
        except OSError:
            if i == attempts - 1:
                raise
        time.sleep(2**i)
    raise IOError(f"could not download {url} after {attempts} attempts")


def main() -> None:
    import warnings

    import astropy.units as u
    from astropy.coordinates import FK5, SkyCoord
    from astropy.utils import iers

    warnings.simplefilter("ignore")
    iers.conf.auto_download = False

    sky = json.loads(_get(LINES_URL))
    cons, segments, needed = [], [], set()
    for c in sky["constellations"]:
        abbr = c["id"].split()[-1]
        latin = c.get("common_name", {}).get("native") or abbr
        cons.append((abbr, latin))
        for poly in c["lines"]:
            hips = [h for h in poly if isinstance(h, int)]
            for a, b in zip(hips, hips[1:]):
                segments.append((abbr, a, b))
                needed.update((a, b))

    rows = []
    reader = csv.DictReader(io.StringIO(_get(HYG_URL).decode("utf-8")))
    for r in reader:
        if r["id"] == "0":  # the Sun
            continue
        hip = int(r["hip"]) if r["hip"] else None
        mag = float(r["mag"])
        if mag <= MAG_LIMIT or (hip is not None and hip in needed):
            rows.append((hip, float(r["ra"]) * 15.0, float(r["dec"]), mag, r["proper"], r["con"]))

    c = SkyCoord(ra=[x[1] for x in rows] * u.deg, dec=[x[2] for x in rows] * u.deg, frame="icrs")
    p = c.transform_to(FK5(equinox=EQUINOX))
    out = HERE / "data"
    out.mkdir(exist_ok=True)
    with open(out / "stars.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["hip", "ra_deg", "dec_deg", "mag", "name", "con"])
        for (hip, _, _, mag, name, con), ra, dec in zip(rows, p.ra.deg, p.dec.deg):
            w.writerow([hip or "", f"{ra:.5f}", f"{dec:.5f}", f"{mag:.2f}", name, con])
    with open(out / "constellation_lines.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["con", "hip1", "hip2"])
        w.writerows(segments)
    with open(out / "constellations.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["con", "latin"])
        w.writerows(cons)
    print(f"{len(rows)} stars, {len(segments)} line segments, {len(cons)} constellations -> {out}")


if __name__ == "__main__":
    main()
