"""Package a print job into one zip: freshly built + checked STLs, previews,
per-model print notes and a one-page JOB.md with totals and a checklist.

The zip is the hand-off to the official Anycubic tools: download it on a
phone or computer, open the STLs in Anycubic Slicer Next / the Anycubic app,
and send to the printer from there.
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from datetime import date
from pathlib import Path

from .build import PartResult, build_model, load_model
from .profile import load_printer

MODELS_DIR = Path(__file__).resolve().parent.parent / "models"
BUNDLES_DIR = Path(__file__).resolve().parent.parent / "bundles"


def parse_target(target: str) -> tuple[Path, str | None]:
    """'word-part-tiles:bases' -> (models/word-part-tiles, 'bases')."""
    slug, _, part = target.partition(":")
    path = Path(slug)
    if not (path / "model.py").exists():
        path = MODELS_DIR / slug
    if not (path / "model.py").exists():
        raise FileNotFoundError(f"No model {slug!r} (looked for {path / 'model.py'})")
    return path, part or None


def _group(targets: list[str]) -> dict[Path, set[str] | None]:
    """Merge targets per model; None means "all parts" and wins over a part list."""
    groups: dict[Path, set[str] | None] = {}
    for t in targets:
        path, part = parse_target(t)
        if part is None or groups.get(path, set()) is None:
            groups[path] = None
        else:
            groups.setdefault(path, set()).add(part)
    return groups


def make_bundle(
    targets: list[str],
    name: str | None = None,
    overrides: dict | None = None,
    material: str | None = None,
    out_dir: str | Path | None = None,
) -> Path:
    if not targets:
        raise ValueError("Nothing to bundle: name at least one model")
    if overrides and len({t.partition(':')[0] for t in targets}) > 1:
        raise ValueError("--set overrides only apply when bundling a single model")
    name = name or "-".join(t.replace(":", "-") for t in targets)
    out_dir = Path(out_dir) if out_dir else BUNDLES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / name
        rows: list[tuple[str, PartResult, dict]] = []
        notes: dict[str, list[str]] = {}
        for model_dir, parts in _group(targets).items():
            slug = model_dir.name
            meta = getattr(load_model(model_dir), "META", {})
            build_dir = Path(tmp) / "build" / slug
            results = build_model(model_dir, overrides, out_dir=build_dir, material=material, only=parts)
            bad = [r.name for r in results if not r.report.ok]
            if bad:
                raise RuntimeError(f"Not bundling — failed printability check: {', '.join(bad)}")
            notes[slug] = meta.get("notes", [])
            (root / "notes").mkdir(parents=True, exist_ok=True)
            (root / "previews").mkdir(exist_ok=True)
            shutil.copy(build_dir / "PRINT.md", root / "notes" / f"{slug}-PRINT.md")
            for r in results:
                shutil.copy(r.stl, root / r.stl.name)
                shutil.copy(r.preview, root / "previews" / f"{r.name}.png")
                rows.append((slug, r, meta))

        (root / "JOB.md").write_text(_job_sheet(name, rows, notes, material))
        zip_path = out_dir / f"{name}.zip"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for f in sorted(root.rglob("*")):
                if f.is_file():
                    z.write(f, f.relative_to(root.parent))
    return zip_path


def _fmt_time(secs: float) -> str:
    h, rem = divmod(int(round(secs)), 3600)
    return f"{h}h {rem // 60:02d}m" if h else f"{rem // 60}m"


def _job_sheet(name: str, rows, notes: dict, material: str | None) -> str:
    p = load_printer()
    total_s = sum(r.report.estimate["seconds"] for _, r, _ in rows if r.report.estimate)
    total_g = sum(r.report.estimate["grams"] for _, r, _ in rows if r.report.estimate)
    lines = [
        f"# Print job: {name}",
        "",
        f"{date.today().isoformat()} · {p.name} · {len(rows)} file(s) · "
        f"~{_fmt_time(total_s)} · ~{total_g:.0f} g filament (estimates ±30 %; the slicer is authoritative)",
        "",
        "| # | File | Material | Supports | Time | Filament |",
        "|---|---|---|---|---|---|",
    ]
    for i, (slug, r, meta) in enumerate(rows, 1):
        mat = (material or meta.get("material", "PLA")).upper()
        est = r.report.estimate or {}
        lines.append(
            f"| {i} | `{r.stl.name}` | {mat} | {'yes' if meta.get('supports') else 'no'} | "
            f"{_fmt_time(est.get('seconds', 0))} | {est.get('grams', 0):.0f} g |"
        )
    from .build import color_change_note

    seen = set()
    for slug, _, meta in rows:
        if meta.get("color_change_z") is not None and slug not in seen:
            seen.add(slug)
            lines += ["", f"{slug}: " + color_change_note(float(meta["color_change_z"]))]
    lines += [
        "",
        "## Send it to the printer",
        "",
        "1. Open the `.stl` files in **Anycubic Slicer Next** (or the Anycubic app) with the Kobra 2 Plus profile.",
        "2. Keep the orientation as exported — every file is already placed flat-side-down for printing.",
        "3. Slice, check the layer preview, then send to the printer through your Anycubic account.",
        "",
        "## Before each print",
        "",
        "- [ ] Bed is clear and the PEI sheet is clean",
        "- [ ] Right filament (and colour) loaded — see notes below",
        "- [ ] Someone is around for the first layer",
        "",
        "## Model notes",
        "",
    ]
    for slug, ns in notes.items():
        lines.append(f"**{slug}**")
        lines += [f"- {n}" for n in ns] or ["- (none)"]
        lines.append("")
    lines.append("Previews are in `previews/`; full printability reports are in `notes/`.")
    return "\n".join(lines) + "\n"
