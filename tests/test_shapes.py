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
                + shapes.frame_edge_cover(style, r, K, RADIUS, COLOR)
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


def test_frame_edge_cover_straddles_the_edge():
    r = RECTS["wide"]
    x0, y0, x1, y1 = r
    mid = (y0 + y1) / 2
    for style in STYLES:
        (ring, _rgba), = shapes.frame_edge_cover(style, r, K, RADIUS, COLOR)
        assert covered((x0 - 0.5, mid), ring) and covered((x0 + 0.5, mid), ring), style
        assert not covered((x0 + 10.0, mid), ring), style  # never reaches the text padding


def test_frame_edge_cover_hides_blenders_frame_shadow_but_stays_inside_the_body():
    # Blender's frame drop shadow reaches ~3.5 units past the edge.
    for style in ("CAT", "PAW", "LOAF"):
        for name, r in RECTS.items():
            x0, y0, x1, y1 = r
            (ring, _rgba), = shapes.frame_edge_cover(style, r, K, RADIUS, COLOR)
            body, _extras = shapes.parts(style, r, K, RADIUS)
            for p in ((x1 + 3.5, (y0 + y1) / 2), ((x0 + x1) / 2, y0 - 3.5)):
                assert covered(p, ring), f"{style}/{name}: shadow uncovered at {p}"
            outer = (x1 + COVER, (y0 + y1) / 2)
            assert covered(outer, body), f"{style}/{name}: cover ring sticks out of the body"
            # Even when the on-screen shadow is wider than the margin, stay inside the body.
            (wide, _rgba), = shapes.frame_edge_cover(style, r, K, RADIUS, COLOR, shadow_px=50.0)
            xs = [x for x, _y in wide]
            assert max(xs) <= x1 + shapes.BODY_MARGIN[style], f"{style}/{name}: capped cover too wide"


COVER = shapes.COVER_OUTSIDE - 0.1


def test_frame_edge_cover_never_pokes_out_of_the_body():
    # Corners included: the cover must not add bumps to the cat outline.
    for style in ("CAT", "PAW", "LOAF"):
        for name, r in RECTS.items():
            body, _extras = shapes.parts(style, r, K, RADIUS)
            for shadow_px in (0.0, 9.0, 50.0):
                (ring, _rgba), = shapes.frame_edge_cover(style, r, K, RADIUS, COLOR, shadow_px)
                out = [p for p in ring if not covered(p, body)]
                assert not out, f"{style}/{name}/{shadow_px}: cover outside body at {out[:2]}"


if __name__ == "__main__":
    # Allows running without pytest: python3 tests/test_shapes.py
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print(f"{len(tests)} passed")
