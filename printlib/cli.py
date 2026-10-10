"""`printlib` command line. Run `python -m printlib --help`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .profile import load_printer

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"

TEMPLATE = '''"""{title}."""

from printlib.shapes import box, difference, hole, on_bed, union  # noqa: F401
from printlib.profile import load_printer

P = load_printer()

META = {{
    "title": "{title}",
    "description": "TODO: what it is and what it's for.",
    "material": "PLA",
    "infill": 0.15,
    "supports": False,
    "notes": [],
}}

PARAMS = {{
    "width": 40.0,
    "depth": 30.0,
    "height": 20.0,
}}


def build(width, depth, height):
    body = box(width, depth, height, r=3, bottom_chamfer=P.design["first_layer_chamfer"])
    return on_bed(body)
'''


def cmd_build(a) -> int:
    from .build import build_model, load_model, parse_overrides

    targets = [Path(t) for t in a.models] or sorted(d for d in MODELS_DIR.iterdir() if (d / "model.py").exists())
    status = 0
    for t in targets:
        if not t.exists() and (MODELS_DIR / t).exists():
            t = MODELS_DIR / t
        mod = load_model(t)
        overrides = parse_overrides(a.set, getattr(mod, "PARAMS", {}))
        results = build_model(t, overrides, out_dir=a.out, material=a.material, preview=not a.no_preview)
        for r in results:
            print(f"wrote {r.stl}" + ("" if a.no_preview else f"  (+ {r.preview.name})"))
            if not a.quiet:
                print(r.report.to_text())
                print()
            if not r.report.ok:
                status = 1
    return status


def cmd_check(a) -> int:
    from .check import check_mesh
    from .meshio import load_mesh

    status = 0
    for f in a.files:
        rep = check_mesh(load_mesh(f), name=Path(f).name, material=a.material, infill=a.infill, supports=a.supports)
        print(rep.to_text() if not a.json else json.dumps({"ok": rep.ok, "stats": rep.stats, "findings": [vars(x) for x in rep.findings]}, indent=2))
        print()
        status |= 0 if rep.ok else 1
    return status


def cmd_render(a) -> int:
    from .meshio import load_mesh
    from .render import render

    out = a.out or str(Path(a.file).with_suffix(".png"))
    render(load_mesh(a.file), out, views=tuple(a.views.split(",")), title=Path(a.file).name)
    print(f"wrote {out}")
    return 0


def cmd_orient(a) -> int:
    from .meshio import export_stl, load_mesh
    from .orient import best_orientation, place_on_bed

    mesh = load_mesh(a.file)
    if a.place_only:
        out_mesh, info = place_on_bed(mesh), {}
    else:
        out_mesh, info = best_orientation(mesh)
    out = a.out or str(Path(a.file).with_name(Path(a.file).stem + "-oriented.stl"))
    export_stl(out_mesh, out)
    print(f"wrote {out}")
    for k, v in info.items():
        print(f"  {k}: {v}")
    return 0


def cmd_new(a) -> int:
    d = MODELS_DIR / a.slug
    if d.exists():
        print(f"{d} already exists", file=sys.stderr)
        return 1
    d.mkdir(parents=True)
    title = a.title or a.slug.replace("-", " ").capitalize()
    (d / "model.py").write_text(TEMPLATE.format(title=title))
    (d / "README.md").write_text(f"# {title}\n\nTODO: purpose, how it's used, assembly notes.\n\nSee [PRINT.md](PRINT.md) for generated print notes.\n")
    print(f"created {d}/model.py and README.md — edit, then `python -m printlib build {a.slug}`")
    return 0


def cmd_info(a) -> int:
    p = load_printer()
    if a.material:
        m = p.material(a.material)
        print(f"{m.name}: nozzle {m.nozzle} °C, bed {m.bed} °C, fan {m.fan}%, speed {m.speed} mm/s, density {m.density} g/cm³")
        print(f"  {m.notes}")
        return 0
    print(p.name)
    print(f"  build volume   {p.build_volume}  (usable {p.usable_volume})")
    print(f"  nozzle         {p.nozzle} mm, max {p.spec['max_nozzle_temp']} °C; bed max {p.spec['max_bed_temp']} °C")
    print("  design rules:")
    for k, v in p.design.items():
        print(f"    {k:<22} {v}")
    print("  fit clearances (per side):")
    for k, v in p.tolerances.items():
        print(f"    {k:<22} {v}")
    print("  materials: " + ", ".join(p.materials))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="printlib", description="STL tooling for the Anycubic Kobra 2 Plus")
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build", help="build model(s) in models/ to STL + preview + PRINT.md")
    b.add_argument("models", nargs="*", help="model dirs or slugs (default: all)")
    b.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="override a PARAM")
    b.add_argument("--out", help="output dir (default: the model dir)")
    b.add_argument("--material")
    b.add_argument("--no-preview", action="store_true")
    b.add_argument("-q", "--quiet", action="store_true")
    b.set_defaults(fn=cmd_build)

    c = sub.add_parser("check", help="printability report for STL/3MF/OBJ files")
    c.add_argument("files", nargs="+")
    c.add_argument("--material", default="PLA")
    c.add_argument("--infill", type=float, default=0.15)
    c.add_argument("--supports", action="store_true", help="supports are planned; downgrade overhang warnings")
    c.add_argument("--json", action="store_true")
    c.set_defaults(fn=cmd_check)

    r = sub.add_parser("render", help="PNG preview of a mesh")
    r.add_argument("file")
    r.add_argument("--out")
    r.add_argument("--views", default="iso,front,right,top")
    r.set_defaults(fn=cmd_render)

    o = sub.add_parser("orient", help="auto-orient a mesh for printing (or just drop it on the bed)")
    o.add_argument("file")
    o.add_argument("--out")
    o.add_argument("--place-only", action="store_true")
    o.set_defaults(fn=cmd_orient)

    n = sub.add_parser("new", help="scaffold models/<slug>/")
    n.add_argument("slug")
    n.add_argument("--title")
    n.set_defaults(fn=cmd_new)

    i = sub.add_parser("info", help="show printer profile / material settings")
    i.add_argument("--material")
    i.set_defaults(fn=cmd_info)

    a = ap.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
