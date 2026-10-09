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
    for style in ("PEEK",):  # body shaped exactly like the frame
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
                # Head and paws sit in the reserved header; rear end and tail hang below the note.
                assert y >= y1 - 14.0 or y <= y0 + 1e-6, f"{name}: peek decoration in the text area at y={y}"


MARGIN_STYLES = ("CAT", "PAW", "LOAF", "TAIL")  # bodies that extend past the frame on every side


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


def _bbox(points):
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def test_loaf_and_tail_ears_sit_on_the_head():
    for style, getter in (("LOAF", shapes._loaf), ("TAIL", shapes._kitty)):
        for name, r in RECTS.items():
            outline = getter(r, K)["outline"]
            core = shapes.polygon(shapes.rounded_points(*outline))
            if style == "LOAF":
                core += getter(r, K)["body"]  # body + domed head
            for ear in getter(r, K)["ears"]:
                assert all(covered(p, core) for p in ear[:2]), f"{style}/{name}: ear base floats off the head"
                assert not covered(ear[2], core), f"{style}/{name}: ear tip buried in the head"
                # Ears belong to the left (head) end.
                assert ear[2][0] < (r[0] + r[2]) / 2, f"{style}/{name}: ear not on the head end"


def test_tail_shape_paw_hangs_down_left_as_a_pointer():
    for name, r in RECTS.items():
        x0, y0, x1, y1 = r
        leg = shapes._kitty(r, K)["leg"]
        lo_x, lo_y, _hx, _hy = _bbox(leg)
        assert lo_y < y0 - 40, f"{name}: paw doesn't hang below the note"
        assert lo_x < x0, f"{name}: paw should point down-left"


def test_peek_cat_sits_behind_the_note_except_its_paws():
    r = RECTS["wide"]
    x0, y0, x1, y1 = r
    fur = (*shapes.FUR, 1.0)
    under = shapes.under("PEEK", r, K, COLOR, RADIUS)
    body_i = next(i for i, (_t, rgba) in enumerate(under) if rgba == (*COLOR, 1.0))
    behind = [i for i, (_t, rgba) in enumerate(under) if rgba == fur]
    assert len(behind) == 3 and max(behind) < body_i, "head, rear and tail should be drawn before the note body"
    # In front of the note, only the paws (and their toe lines) reach into the box.
    p = shapes._peek(r, K)
    for tris, rgba in shapes.over("PEEK", r, K, COLOR, RADIUS):
        inside = [pt for pt in tris if x0 < pt[0] < x1 and y0 + 1e-6 < pt[1] < y1 - 1e-6]
        if inside:
            assert rgba[:3] == shapes.FUR or rgba == shapes.mix(shapes.FUR, shapes.WHITE, 0.25), "only paws may overlap"
            assert all(abs(pt[1] - y1) <= 0.25 * p["hr"] for pt in inside), "paw reaches too far into the note"


def test_peek_rear_end_hangs_below_the_note():
    for name, r in RECTS.items():
        x0, y0, x1, y1 = r
        p = shapes._peek(r, K)
        for piece in ("butt", "tail"):
            _lx, _ly, _hx, hy = _bbox(p[piece])
            assert hy <= y0 + 1e-6, f"{name}: {piece} reaches into the note"
        assert _bbox(p["tail"])[2] > p["cx"] + p["hr"], f"{name}: tail should point right"


def test_paw_claws_point_up_from_behind_the_toes_and_pad():
    for name, r in RECTS.items():
        x0, y0, x1, y1 = r
        p = shapes._paw(r, K)
        for (cx, cy, tr), claw in zip(p["toes"], p["claws"]):
            assert abs(claw[2][0] - cx) < 1e-9, f"{name}: claw should point straight up"
            assert claw[2][1] > cy + tr, f"{name}: claw tip hidden in the toe"
            assert all(covered(b, shapes.circle(cx, cy, tr)) for b in claw[:2]), f"{name}: claw base not behind the toe"
        # Claws are painted before (under) the body, so the toe fur hides their bases.
        layers = shapes.under("PAW", r, K, COLOR, RADIUS)
        claw_i = next(i for i, (_t, rgba) in enumerate(layers) if rgba[:3] == shapes.CLAW)
        body_i = next(i for i, (_t, rgba) in enumerate(layers) if rgba == (*COLOR, 1.0))
        assert claw_i < body_i, f"{name}: claws drawn on top of the toes"
        # Pink pad leaves a fur rim inside the frame.
        pad = shapes._paw_pad(r, K)
        lx, ly, hx, hy = _bbox(pad)
        assert lx > x0 and ly > y0 and hx < x1 and hy < y1, f"{name}: pad should sit inside the frame"
    assert shapes.text_backdrop("PAW", COLOR) != tuple(COLOR)
    assert shapes.text_backdrop("CAT", COLOR) == tuple(COLOR)


def test_belly_flows_straight_into_the_tail():
    for style, getter in (("LOAF", shapes._loaf), ("TAIL", shapes._kitty)):
        for name, r in RECTS.items():
            p = getter(r, K)
            X0, Y0, X1, Y1, radii = p["outline"]
            lx, ly, hx, hy = _bbox(p["tail"])
            assert abs(ly - Y0) < 1.0, f"{style}/{name}: tail bottom should line up with the belly ({ly} vs {Y0})"
            assert hx > X1 + 10, f"{style}/{name}: tail should sweep out past the rump"


def test_rump_corner_matches_the_head_corner():
    for style, getter in (("LOAF", shapes._loaf), ("TAIL", shapes._kitty)):
        for name, r in RECTS.items():
            tl, tr, _br, _bl = getter(r, K)["outline"][4]
            assert tl == tr, f"{style}/{name}: rump corner {tr} != head corner {tl}"


def test_kitty_tail_rises_above_its_back_and_leg_is_slim():
    for name, r in RECTS.items():
        p = shapes._kitty(r, K)
        X0, Y0, X1, Y1, _radii = p["outline"]
        assert _bbox(p["tail"])[3] > Y1, f"{name}: tail should rise above the back"
        # Where the leg leaves the body, it's no wider than ~half the body height.
        arm = p["leg"][:6]  # the arm polygon itself (two triangles), not the paw/elbow circles
        at_belly = [x for x, y in arm if abs(y - (Y0 + 2)) < 2.5]
        assert at_belly and max(at_belly) - X0 <= 0.5 * (Y1 - Y0) + 1, f"{name}: leg too thick at the base"


def test_peek_tail_hangs_from_the_middle():
    for name, r in RECTS.items():
        p = shapes._peek(r, K)
        lx, _ly, _hx, hy = _bbox(p["tail"])
        assert abs(lx + 0.22 * p["hr"] - p["cx"]) < 0.1 * p["hr"], f"{name}: tail should start at the center"


def test_kitty_arm_meets_the_body_with_no_gap():
    for name, r in RECTS.items():
        p = shapes._kitty(r, K)
        X0, Y0, _X1, _Y1, radii = p["outline"]
        corner = radii[3]
        body_and_leg = shapes.polygon(shapes.rounded_points(*p["outline"])) + p["leg"]
        # The bottom-left corner box, where the rounded chin used to leave a notch.
        for i in range(1, 10):
            for j in range(1, 10):
                pt = (X0 + corner * i / 10, Y0 + corner * j / 10)
                assert covered(pt, body_and_leg), f"{name}: gap between arm and body at {pt}"


def test_cat_head_ears_match_loaf_and_tail_ears():
    for name, r in RECTS.items():
        for (ear, visible), outer_side in zip(shapes._cat_ear_geometry(r, K), (1, -1)):
            outer_x, inner_x = ear[0][0], ear[1][0]
            base_w = abs(inner_x - outer_x)
            height = ear[2][1] - visible[0][1]
            # Tail/Loaf proportions (visible height ~1.15-1.35x the base), not a spike.
            assert 1.0 <= height / base_w <= 1.5, f"{name}: ear proportions {height / base_w:.2f}"
            # Apex just inside the outer edge, like the Tail ears.
            inset = (ear[2][0] - outer_x) * outer_side
            assert 0 < inset <= 0.2 * base_w, f"{name}: apex should sit just inside the outer edge"
        # Pink inner ear is centered on the visible ear.
        layers = shapes.over("CAT", r, K, COLOR, RADIUS)
        for (ear, visible), (pink, _rgba) in zip(shapes._cat_ear_geometry(r, K), layers[:2]):
            vc = (sum(p[0] for p in visible) / 3, sum(p[1] for p in visible) / 3)
            pc = (sum(p[0] for p in pink) / len(pink), sum(p[1] for p in pink) / len(pink))
            ear_w = abs(visible[1][0] - visible[0][0])
            assert abs(vc[0] - pc[0]) < 0.1 * ear_w, f"{name}: pink not centered horizontally"
            assert covered(pc, shapes.polygon(visible)), f"{name}: pink outside the visible ear"


def test_cat_head_pink_sits_flat_on_the_head_line():
    for name, r in RECTS.items():
        layers = shapes.over("CAT", r, K, COLOR, RADIUS)
        for (ear, visible), (pink, _rgba) in zip(shapes._cat_ear_geometry(r, K), layers[:2]):
            lows = sorted(pink, key=lambda p: p[1])[:2]
            assert abs(lows[0][1] - lows[1][1]) < 1e-6, f"{name}: pink bottom not flat"
            assert abs(lows[0][1] - (visible[0][1] + 1.0)) < 1e-6, f"{name}: pink bottom not on the head line"


def test_peek_asterisk_sits_on_the_rear_just_above_the_tail():
    for name, r in RECTS.items():
        p = shapes._peek(r, K)
        pink = shapes.mix(shapes.FUR, shapes.PINK, 0.6)
        stars = [t for t, rgba in shapes.over("PEEK", r, K, COLOR, RADIUS) if rgba == pink and min(y for _x, y in t) < r[1]]
        assert len(stars) == 3, f"{name}: asterisk should have three strokes"
        pts = [pt for t in stars for pt in t]
        assert all(covered(pt, p["butt"]) for pt in pts), f"{name}: asterisk off the rear end"
        assert abs(sum(x for x, _y in pts) / len(pts) - p["cx"]) < 1e-6, f"{name}: asterisk not centered"


def test_kitty_elbow_sits_just_behind_the_arm():
    for name, r in RECTS.items():
        p = shapes._kitty(r, K)
        X0, Y0, X1, Y1, _radii = p["outline"]
        aw = max(x for x, y in p["leg"][:6] if abs(y - (Y0 + 2)) < 1e-6)  # arm's belly point
        r_e = shapes.ELBOW_R
        lowest_x = [x for x, y in p["leg"] if Y0 - 2 - r_e - 0.5 < y < Y0 - 2 - r_e + 1.5]  # bottom of the elbow paw
        assert lowest_x, name
        ex = sum(lowest_x) / len(lowest_x)
        assert aw < ex < aw + 1.5 * (aw - X0), f"{name}: elbow at {ex:.0f}, arm meets belly at {aw:.0f}"


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
