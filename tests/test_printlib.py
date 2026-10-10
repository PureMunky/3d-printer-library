from pathlib import Path

import numpy as np
import pytest
import trimesh

from printlib.build import build_model, parse_overrides
from printlib.check import ERROR, WARN, check_mesh
from printlib.meshio import to_trimesh
from printlib.orient import best_orientation
from printlib.profile import load_printer
from printlib.shapes import box, cylinder, difference, label_face, on_bed, teardrop, text2d

MODELS = Path(__file__).resolve().parent.parent / "models"


def codes(report, level=None):
    return {f.code for f in report.findings if level is None or f.level == level}


def test_profile():
    p = load_printer()
    assert p.build_volume == (320, 320, 400)
    assert p.usable_volume[0] <= p.build_volume[0]
    assert p.material("pla").nozzle == 210
    assert p.tol("slide") > p.tol("press")


def test_box_is_valid_and_on_bed():
    m = box(30, 20, 10, r=3, bottom_chamfer=0.4)
    t = to_trimesh(m)
    assert t.is_watertight
    assert np.allclose(t.bounds, [[-15, -10, 0], [15, 10, 10]], atol=1e-4)
    rep = check_mesh(t)
    assert rep.ok and not codes(rep, WARN)


def test_too_big_is_error():
    rep = check_mesh(to_trimesh(box(500, 20, 10)))
    assert "too-big" in codes(rep, ERROR)


def test_diagonal_fit_is_warning():
    rep = check_mesh(to_trimesh(box(350, 30, 10)))
    assert "fits-diagonally" in codes(rep, WARN)


def test_overhang_detected_and_teardrop_avoids_it():
    # Mushroom: wide cap on a thin stem -> big flat overhang
    mush = on_bed(box(10, 10, 20) + box(40, 40, 5).translate((0, 0, 20)))
    rep = check_mesh(to_trimesh(mush))
    assert codes(rep, WARN) & {"overhang", "long-bridge"}

    block = box(30, 20, 20)
    round_hole = difference(block, cylinder(8, 40).rotate((0, 90, 0)).translate((-20, 0, 10)))
    tear_hole = difference(block, teardrop(8, 40, axis="x").translate((0, 0, 10)))
    assert "overhang" in codes(check_mesh(to_trimesh(round_hole)), WARN)
    assert "overhang" not in codes(check_mesh(to_trimesh(tear_hole)), WARN)


def test_thin_wall_warning():
    thin = difference(box(30, 30, 10), box(29.2, 29.2, 10).translate((0, 0, 1)))  # 0.4 mm walls
    assert "thin-wall" in codes(check_mesh(to_trimesh(thin)), WARN)
    ok = difference(box(30, 30, 10), box(26.8, 26.8, 10).translate((0, 0, 1)))  # 1.6 mm walls
    assert "thin-wall" not in codes(check_mesh(to_trimesh(ok)), WARN)


def test_floating_body_and_open_mesh():
    a = to_trimesh(box(10, 10, 10))
    b = to_trimesh(box(10, 10, 10).translate((20, 0, 5)))
    assert "floating-body" in codes(check_mesh(trimesh.util.concatenate([a, b])), ERROR)
    opened = a.copy()
    opened.update_faces(np.arange(len(opened.faces) - 1))
    assert "not-watertight" in codes(check_mesh(opened), ERROR)


def test_text_and_labels():
    cs = text2d("Hi 42", 8)
    assert cs.area() > 20
    lo, hi = np.array(cs.bounds()).reshape(2, 2)
    assert abs((lo + hi)[0]) < 1e-6  # centred
    base = box(40, 20, 5)
    engraved = label_face(base, cs, "+z")
    raised = label_face(base, cs, "+z", raised=True)
    assert engraved.volume() < base.volume() < raised.volume()


def test_orient_flips_upside_down_cone():
    cone = to_trimesh(cylinder(30, 30, d2=0.0))  # tip up, flat base down
    cone.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [1, 0, 0]))
    oriented, info = best_orientation(cone)
    assert info["contact_mm2"] > 500
    assert oriented.bounds[0][2] == pytest.approx(0, abs=1e-6)


def test_parse_overrides_types():
    d = {"w": 10.0, "n": 2, "flag": False, "label": "", "xs": [0.1]}
    out = parse_overrides(["w=12.5", "n=3", "flag=true", "label=Hi there", "xs=[0.2, 0.3]"], d)
    assert out == {"w": 12.5, "n": 3, "flag": True, "label": "Hi there", "xs": [0.2, 0.3]}
    with pytest.raises(KeyError):
        parse_overrides(["nope=1"], d)


@pytest.mark.parametrize("model", sorted(p.name for p in MODELS.iterdir() if (p / "model.py").exists()))
def test_every_model_builds_printable(model, tmp_path):
    results = build_model(MODELS / model, out_dir=tmp_path, preview=False)
    assert results
    for r in results:
        assert r.report.ok, r.report.to_text()
        assert r.stl.stat().st_size > 0


def test_render_does_not_flag_exact_45_degree_chamfers(tmp_path):
    from PIL import Image

    from printlib.render import RED, render
    from printlib.shapes import polygon
    from manifold3d import Manifold

    # A ledge whose underside is exactly 45° — printable, so it must not render red.
    wedge = Manifold.extrude(polygon([(0, 0), (10, 0), (20, 10), (20, 20), (0, 20)]), 10).rotate((90, 0, 0))
    out = render(on_bed(wedge), tmp_path / "w.png", views=("bottom",))
    px = np.asarray(Image.open(out).convert("RGB")).reshape(-1, 3).astype(int)
    red_like = (px[:, 0] > 150) & (px[:, 1] < 100) & (px[:, 2] < 100)
    assert not red_like.any()
    assert RED[0] > 150  # sanity: the check above would catch the overhang colour


def test_thin_wall_ignores_sharp_corners_on_thick_features():
    from printlib.shapes import offset, rect

    # Raised plus signs with 1.2 mm strokes: lots of square corners, nothing thin.
    plus = rect(6, 1.2) + rect(1.2, 6)
    base = box(60, 20, 2)
    for i in range(6):
        base = label_face(base, plus.translate((-25 + i * 10, 0)), "+z", depth=0.8, raised=True)
    assert "thin-wall" not in codes(check_mesh(to_trimesh(base)), WARN)
    # Same pattern with 0.5 mm strokes must still be flagged.
    thin = box(60, 20, 2)
    for i in range(6):
        thin = label_face(thin, (rect(6, 0.5) + rect(0.5, 6)).translate((-25 + i * 10, 0)), "+z", depth=0.8, raised=True)
    assert "thin-wall" in codes(check_mesh(to_trimesh(thin)), WARN)
    _ = offset


def test_offset_has_no_micro_edges():
    from manifold3d import CrossSection

    from printlib.shapes import offset, rect

    # Circle + rectangle neck: Clipper leaves ~1e-8 mm vertex pairs here without simplify.
    knob = CrossSection.circle(4).translate((4, 0)) + rect(3, 4.4).translate((1, 0))
    pts = np.vstack(offset(knob, 0.25).to_polygons())
    seg = np.linalg.norm(np.diff(np.vstack([pts, pts[:1]]), axis=0), axis=1)
    assert seg.min() > 1e-4


def test_built_stl_on_disk_is_watertight(tmp_path):
    from printlib.meshio import load_mesh

    for r in build_model(MODELS / "word-part-tiles", out_dir=tmp_path, preview=False):
        assert load_mesh(r.stl).is_watertight, r.stl.name


def test_render_outlines_shallow_relief(tmp_path):
    from PIL import Image

    from printlib.render import render
    from printlib.shapes import rect

    plate = label_face(box(150, 40, 3), rect(10, 10), "+z", depth=0.6, raised=True)
    out = render(plate, tmp_path / "r.png", views=("top",), size=600)
    px = np.asarray(Image.open(out).convert("L"))
    # Edges of the 0.6 mm raised square sit near the image centre; they must be drawn dark.
    centre = px[320:405, 260:340]  # sheet header is 62 px; square is centred on (362, 300)
    assert (centre < 60).sum() > 40


def test_bundle_zips_selected_parts_with_job_sheet(tmp_path):
    import zipfile

    from printlib.bundle import make_bundle

    z = make_bundle(["tolerance-test:peg", "calibration-cube"], name="job", out_dir=tmp_path)
    names = set(zipfile.ZipFile(z).namelist())
    assert {"job/JOB.md", "job/tolerance-test-peg.stl", "job/calibration-cube.stl",
            "job/previews/tolerance-test-peg.png", "job/notes/tolerance-test-PRINT.md"} <= names
    assert "job/tolerance-test-plate.stl" not in names  # only the requested part
    sheet = zipfile.ZipFile(z).read("job/JOB.md").decode()
    assert "2 file(s)" in sheet and "Before each print" in sheet


def test_bundle_rejects_unknown_part_and_multi_model_overrides(tmp_path):
    from printlib.bundle import make_bundle

    with pytest.raises(KeyError):
        make_bundle(["tolerance-test:nope"], out_dir=tmp_path)
    with pytest.raises(ValueError):
        make_bundle(["tolerance-test", "calibration-cube"], overrides={"size": 10.0}, out_dir=tmp_path)


def test_bundle_merges_parts_of_same_model():
    from printlib.bundle import _group

    g = _group(["tolerance-test:peg", "tolerance-test:plate", "calibration-cube", "calibration-cube:x"])
    assert {k.name: v for k, v in g.items()} == {"tolerance-test": {"peg", "plate"}, "calibration-cube": None}
