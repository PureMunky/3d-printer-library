"""Build a parametric model directory into STL + preview + print notes.

A model lives in ``models/<slug>/model.py`` and defines:

    META = {                       # optional
        "title": "Parametric box",
        "description": "...",
        "material": "PLA",         # default material for estimates/notes
        "infill": 0.15,
        "supports": False,         # True if you *intend* supports
        "notes": ["Print lid upside down", ...],
    }
    PARAMS = {"width": 60.0, ...}  # every tunable, with defaults
    def build(**params) -> Manifold | dict[str, Manifold]

Returning a dict produces one STL per part (``<slug>-<part>.stl``).
"""

from __future__ import annotations

import ast
import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType

from manifold3d import Manifold

from .check import Report, check_mesh
from .meshio import export_stl, load_mesh, to_trimesh
from .profile import load_printer
from .render import render
from .shapes import on_bed


@dataclass
class PartResult:
    name: str
    stl: Path
    preview: Path
    report: Report


def load_model(model_dir: str | Path) -> ModuleType:
    model_dir = Path(model_dir)
    path = model_dir / "model.py" if model_dir.is_dir() else model_dir
    spec = importlib.util.spec_from_file_location(f"model_{path.parent.name.replace('-', '_')}", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    if not hasattr(mod, "build"):
        raise AttributeError(f"{path} must define build(**params)")
    return mod


def parse_overrides(pairs: list[str], defaults: dict) -> dict:
    """Parse ["width=80", "label=Hi"] using the default's type."""
    out = {}
    for pair in pairs or []:
        key, _, raw = pair.partition("=")
        if key not in defaults:
            raise KeyError(f"Unknown param {key!r}; available: {sorted(defaults)}")
        default = defaults[key]
        if isinstance(default, bool):
            val = raw.lower() in ("1", "true", "yes", "on")
        elif isinstance(default, (int, float)):
            val = type(default)(float(raw)) if isinstance(default, int) else float(raw)
        elif isinstance(default, str):
            val = raw
        else:
            val = ast.literal_eval(raw)
        out[key] = val
    return out


def build_model(
    model_dir: str | Path,
    overrides: dict | None = None,
    out_dir: str | Path | None = None,
    material: str | None = None,
    preview: bool = True,
    only: set[str] | None = None,
) -> list[PartResult]:
    """Build, export, check and preview a model. `only` limits output to those
    part names (e.g. {"bases"}); unknown names raise KeyError."""
    model_dir = Path(model_dir)
    mod = load_model(model_dir)
    meta = getattr(mod, "META", {})
    params = {**getattr(mod, "PARAMS", {}), **(overrides or {})}
    material = material or meta.get("material", "PLA")
    infill = float(meta.get("infill", 0.15))
    supports = bool(meta.get("supports", False))
    out_dir = Path(out_dir) if out_dir else model_dir
    slug = model_dir.name if model_dir.is_dir() else model_dir.stem

    result = mod.build(**params)
    parts = result if isinstance(result, dict) else {None: result}
    if only:
        missing = set(only) - {k for k in parts if k}
        if missing:
            raise KeyError(f"{slug} has no part(s) {sorted(missing)}; available: {sorted(k for k in parts if k)}")
        parts = {k: v for k, v in parts.items() if k in only}
    results = []
    for part, solid in parts.items():
        if not isinstance(solid, Manifold):
            raise TypeError(f"build() must return Manifold(s), got {type(solid)}")
        if solid.status().name != "NoError" or solid.is_empty():
            raise ValueError(f"Part {part or slug} is empty/invalid: {solid.status().name}")
        solid = on_bed(solid)
        name = f"{slug}-{part}" if part else slug
        mesh = to_trimesh(solid)
        stl = export_stl(mesh, out_dir / f"{name}.stl")
        # Check the file as a slicer will see it (float32 STL, vertices merged
        # by position), not the in-memory solid.
        mesh = load_mesh(stl)
        report = check_mesh(mesh, name=name, material=material, infill=infill, supports=supports)
        png = out_dir / (f"preview-{part}.png" if part else "preview.png")
        if preview:
            render(mesh, png, title=meta.get("title", slug) + (f" — {part}" if part else ""))
        results.append(PartResult(name, stl, png, report))

    write_print_notes(out_dir, slug, meta, params, material, infill, results)
    return results


def color_change_note(z: float) -> str:
    """Slicer instruction for a two-colour print of a single-colour relief."""
    layer = load_printer().design["layer_height"]
    n = round(z / layer) + 1
    return (f"**Optional colour change:** at Z = {z:g} mm (start of layer {n} at {layer} mm layers) — "
            "base colour below, raised details in the second colour. In Anycubic Slicer Next / OrcaSlicer: "
            "slice, drag the layer slider to that layer, right-click > Add colour change.")


def write_print_notes(out_dir: Path, slug: str, meta: dict, params: dict, material: str, infill: float, results: list[PartResult]) -> Path:
    p = load_printer()
    mat = p.material(material)
    lines = [
        f"# {meta.get('title', slug)} — print notes",
        "",
        "_Generated by `printlib build`; do not edit by hand._",
        "",
        f"**Printer:** {p.name} · **Material:** {mat.name} · **Nozzle** {mat.nozzle} °C · **Bed** {mat.bed} °C · "
        f"**Layer** {p.design['layer_height']} mm · **Infill** {infill:.0%} · **Supports:** {'yes' if meta.get('supports') else 'no'}",
        "",
    ]
    if meta.get("description"):
        lines += [meta["description"], ""]
    if meta.get("color_change_z") is not None:
        lines += [color_change_note(float(meta["color_change_z"])), ""]
    if meta.get("notes"):
        lines += ["## Notes", ""] + [f"- {n}" for n in meta["notes"]] + [""]
    lines += ["## Parameters used", "", "| Param | Value |", "|---|---|"]
    lines += [f"| `{k}` | {v} |" for k, v in params.items()]
    lines.append("")
    for r in results:
        lines += [f"## `{r.stl.name}`", "", f"![preview]({r.preview.name})", "", r.report.to_markdown(), ""]
    path = out_dir / "PRINT.md"
    path.write_text("\n".join(lines))
    return path
