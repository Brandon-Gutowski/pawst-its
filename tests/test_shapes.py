# SPDX-FileCopyrightText: 2026 Brandon Gutowski
#
# SPDX-License-Identifier: GPL-3.0-or-later

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pawst_its"))

import shapes  # noqa: E402

STYLES = ["CAT", "PEEK", "PAW", "LOAF", "TAIL"]
RECTS = {
    "wide": (0.0, 0.0, 260.0, 140.0),
    "tall": (0.0, 0.0, 120.0, 400.0),
    "square": (0.0, 0.0, 200.0, 200.0),
    "tiny": (0.0, 0.0, 60.0, 40.0),
}
K = 1.0
RADIUS = 4.0
COLOR = (1.0, 0.9, 0.5)


def triangles(tris):
    return [tris[i:i + 3] for i in range(0, len(tris), 3)]


def inside_triangle(p, a, b, c, eps=1e-6):
    def cross(o, u, v):
        return (u[0] - o[0]) * (v[1] - o[1]) - (u[1] - o[1]) * (v[0] - o[0])

    d1, d2, d3 = cross(a, b, p), cross(b, c, p), cross(c, a, p)
    has_neg = d1 < -eps or d2 < -eps or d3 < -eps
    has_pos = d1 > eps or d2 > eps or d3 > eps
    return not (has_neg and has_pos)


def covered(p, tris):
    return any(inside_triangle(p, *t) for t in triangles(tris))


def frame_outline(r, inset=0.05):
    """Points along the native frame's rounded-rect edge, nudged slightly inward."""
    x0, y0, x1, y1 = r
    rad = RADIUS
    pts = []
    for (cx, cy), a0 in zip(
        ((x1 - rad, y1 - rad), (x0 + rad, y1 - rad), (x0 + rad, y0 + rad), (x1 - rad, y0 + rad)),
        (0.0, math.pi / 2, math.pi, 3 * math.pi / 2),
    ):
        for i in range(7):
            a = a0 + (math.pi / 2) * i / 6
            pts.append((cx + (rad - inset) * math.cos(a), cy + (rad - inset) * math.sin(a)))
    # Edge midpoints too.
    pts += [((x0 + x1) / 2, y1 - inset), ((x0 + x1) / 2, y0 + inset), (x0 + inset, (y0 + y1) / 2), (x1 - inset, (y0 + y1) / 2)]
    return pts


def test_every_body_covers_the_frame():
    # The note-colored body (not just the silhouette) must hide the frame.
    for style in STYLES:
        for name, r in RECTS.items():
            sil, _extras = shapes.parts(style, r, K, RADIUS)
            missing = [p for p in frame_outline(r) if not covered(p, sil)]
            assert not missing, f"{style}/{name}: frame edge not covered at {missing[:3]}"


def test_rect_styles_do_not_poke_past_rounded_corners():
    # The square corner of the frame's bounding box must NOT be painted,
    # otherwise a sharp corner shows behind the frame's rounded one.
    for style in ("PEEK", "TAIL"):  # bodies shaped exactly like the frame
        for name, r in RECTS.items():
            x0, y0, x1, y1 = r
            sil, _extras = shapes.parts(style, r, K, RADIUS)
            for corner in ((x0 + 0.3, y0 + 0.3), (x1 - 0.3, y0 + 0.3), (x0 + 0.3, y1 - 0.3), (x1 - 0.3, y1 - 0.3)):
                assert not covered(corner, sil), f"{style}/{name}: sharp corner painted at {corner}"


def test_unknown_and_legacy_styles_render_as_cat_head():
    r = RECTS["wide"]
    for legacy in ("", "CLASSIC", "OCTAGON", "DOGEAR"):
        assert shapes.silhouette(legacy, r, K, RADIUS) == shapes.silhouette("CAT", r, K, RADIUS)
        assert shapes.over(legacy, r, K, COLOR, RADIUS) == shapes.over("CAT", r, K, COLOR, RADIUS)


def test_geometry_is_finite_and_complete():
    for style in STYLES:
        for name, r in RECTS.items():
            layers = (
                shapes.under(style, r, K, COLOR, RADIUS, (1.0, 0.6, 0.2, 1.0))
                + shapes.over(style, r, K, COLOR, RADIUS)
                + [(shapes.margin_cover(style, r, K, RADIUS), (*COLOR, 1.0))]
            )
            for tris, rgba in layers:
                assert len(tris) % 3 == 0, f"{style}/{name}: partial triangle"
                assert len(rgba) == 4
                for x, y in tris:
                    assert math.isfinite(x) and math.isfinite(y), f"{style}/{name}: non-finite vertex"


def test_rounded_rect_square_corners_option():
    tris = shapes.rounded_rect(0, 0, 100, 50, 10, corners=(True, True, False, False))
    assert covered((0.2, 0.2), tris)  # bottom-left left square
    assert not covered((0.2, 49.8), tris)  # top-left rounded


def test_halo_surrounds_the_silhouette():
    r = RECTS["wide"]
    for style in STYLES:
        sil = shapes.silhouette(style, r, K, RADIUS)
        ring = shapes.halo(sil, 3.0)
        x0, y0, x1, y1 = r
        # Just outside the frame's left edge, the halo (or the shape itself) is painted.
        assert covered((x0 - 1.0, (y0 + y1) / 2), ring + sil), style


def test_peek_head_and_paws_stay_out_of_the_text_area():
    for name, r in RECTS.items():
        x0, y0, x1, y1 = r
        for tris, _rgba in shapes.over("PEEK", r, K, COLOR, RADIUS):
            for _x, y in tris:
                assert y >= y1 - 14.0, f"{name}: peek decoration dips below the reserved header"


MARGIN_STYLES = ("CAT", "PAW", "LOAF")  # bodies that extend past the frame on every side


def test_margin_cover_hides_frame_outline_and_shadow_everywhere_on_the_body():
    # Blender's frame outline sits on the edge; its drop shadow spreads outward
    # by a fixed number of *pixels*, so at low zoom it can reach the body edge.
    for style in MARGIN_STYLES:
        for name, r in RECTS.items():
            x0, y0, x1, y1 = r
            cover = shapes.margin_cover(style, r, K, RADIUS)
            body, _extras = shapes.parts(style, r, K, RADIUS)
            mx, my = (x0 + x1) / 2, (y0 + y1) / 2
            probes = [(x0 + 0.5, my), (x1 - 0.5, my), (mx, y0 + 0.5), (mx, y1 - 0.5)]  # outline
            for d in (0.5, 3.5, 6.0, 9.0):
                probes += [(x1 + d, my), (mx, y0 - d), (x0 - d, my), (x1 + d * 0.7, y0 - d * 0.7)]
            for p in probes:
                if covered(p, body):  # only points that are part of the cat
                    assert covered(p, cover), f"{style}/{name}: frame shadow/outline visible at {p}"


def test_margin_cover_never_pokes_out_of_the_body():
    for style in MARGIN_STYLES:
        for name, r in RECTS.items():
            body, _extras = shapes.parts(style, r, K, RADIUS)
            cover = shapes.margin_cover(style, r, K, RADIUS)
            out = [p for p in cover if not covered(p, body)]
            assert not out, f"{style}/{name}: cover outside body at {out[:2]}"


def test_margin_cover_leaves_the_frame_interior_alone():
    # Nodes placed on a note must stay visible, and text must never be painted over.
    for style in STYLES:
        for name, r in RECTS.items():
            x0, y0, x1, y1 = r
            cover = shapes.margin_cover(style, r, K, RADIUS)
            for p in ((x0 + 10, y0 + 10), (x1 - 10, y1 - 10), ((x0 + x1) / 2, (y0 + y1) / 2), (x0 + 3, (y0 + y1) / 2)):
                assert not covered(p, cover), f"{style}/{name}: cover paints inside the frame at {p}"


def test_tail_cover_covers_the_tail_base_outside_the_frame_only():
    for style in ("TAIL", "LOAF"):
        r = RECTS["wide"]
        x0, y0, x1, y1 = r
        cover = shapes.margin_cover(style, r, K, RADIUS)
        tail_pts = [p for p in cover if p[0] > x1 + 2]
        assert tail_pts, f"{style}: tail base not covered"
        inset = shapes.COVER_INSET + 1e-6
        between = [p for p in cover if x0 + inset < p[0] < x1 - inset and y0 + 10 < p[1] < y1 - 10]
        assert not between, f"{style}: tail cover reaches into the frame at {between[:2]}"


def test_margin_cover_min_inset_for_low_zoom():
    # Zoomed out (k small), Blender's fixed-width outline is still covered...
    r = (0.0, 0.0, 78.0, 42.0)  # a 260x140 note at k = 0.3
    k = 0.3
    cover = shapes.margin_cover("PEEK", r, k, RADIUS * k, min_inset=5.0)
    assert covered((r[0] + 4.0, 21.0), cover) and covered((39.0, r[1] + 4.0), cover)
    # ...but the inset never eats more than a quarter of a tiny note.
    tiny = (0.0, 0.0, 12.0, 8.0)
    cover = shapes.margin_cover("CAT", tiny, k, RADIUS * k, min_inset=50.0)
    assert not covered((6.0, 4.0), cover)


def test_margin_cover_top_inset_spans_the_name_strip():
    r = RECTS["wide"]
    x0, y0, x1, y1 = r
    cover = shapes.margin_cover("CAT", r, K, RADIUS, top_inset=28.0)
    assert covered(((x0 + x1) / 2, y1 - 20.0), cover)  # Blender's label lives here
    assert not covered(((x0 + x1) / 2, y1 - 40.0), cover)  # body text below stays clear
    # Clamped so a huge header can't swallow the whole note.
    tiny = (0.0, 0.0, 60.0, 40.0)
    assert not covered((30.0, 2.0), shapes.margin_cover("CAT", tiny, K, RADIUS, top_inset=500.0))


def test_clip_tris():
    tri = [(0.0, 0.0), (10.0, 0.0), (0.0, 10.0)]
    right = shapes.clip_tris(tri, 1.0, 0.0, -5.0)  # keep x >= 5
    assert right and all(x >= 5.0 - 1e-9 for x, _y in right)
    assert covered((6.0, 1.0), right) and not covered((4.0, 1.0), right)
    assert shapes.clip_tris(tri, 1.0, 0.0, -20.0) == []


if __name__ == "__main__":
    # Allows running without pytest: python3 tests/test_shapes.py
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print(f"{len(tests)} passed")
