# SPDX-FileCopyrightText: 2026 Brandon Gutowski
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Geometry for the cat styles, as lists of (triangles, rgba) to fill.

All functions take the note rectangle ``r = (x0, y0, x1, y1)`` (y up) in the
current drawing space and ``k``, the size of one note unit in that space, so
the same code serves any zoom level. ``radius`` is the native Frame's corner
radius in that space.

Everything is drawn on top of the node tree, note by note: ``under()``
(shadow, selection halo, anything that sits *behind* the note such as the
peeking cat's body, then the opaque note body), ``margin_cover()``, then
``over()`` (cat features in front of the note). The opaque body also hides
Blender's own Frame node underneath, which still provides selection, moving
and resizing.
"""

import math

SHADOW = (0.0, 0.0, 0.0)
PINK = (1.0, 0.62, 0.72)
WHITE = (1.0, 1.0, 1.0)
FUR = (0.16, 0.16, 0.19)  # the peeking cat is a black cat
EYE = (0.62, 0.86, 0.32)
PUPIL = (0.05, 0.05, 0.06)

_EIGHT_WAYS = [(math.cos(i * math.pi / 4), math.sin(i * math.pi / 4)) for i in range(8)]


# -- primitives ------------------------------------------------------------


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)]


def _segments(radius):
    return max(4, min(48, int(radius * 0.6) + 3))


def _arc_points(cx, cy, rx, a0, a1, segments=None, ry=None):
    ry = rx if ry is None else ry
    n = segments or _segments(max(rx, ry))
    return [
        (cx + rx * math.cos(a0 + (a1 - a0) * i / n), cy + ry * math.sin(a0 + (a1 - a0) * i / n))
        for i in range(n + 1)
    ]


def _fan(cx, cy, pts):
    tris = []
    for a, b in zip(pts, pts[1:]):
        tris += [(cx, cy), a, b]
    return tris


def circle(cx, cy, radius, segments=None):
    if segments is None:
        segments = max(12, min(64, int(radius * 0.8)))
    return _fan(cx, cy, _arc_points(cx, cy, radius, 0.0, 2 * math.pi, segments))


def ellipse(cx, cy, rx, ry):
    return _fan(cx, cy, _arc_points(cx, cy, rx, 0.0, 2 * math.pi, max(16, _segments(max(rx, ry)) * 2), ry))


def ellipse_top(cx, cy, rx, ry):
    """Upper half of an ellipse, sitting on a flat base at ``cy``."""
    return _fan(cx, cy, _arc_points(cx, cy, rx, 0.0, math.pi, max(12, _segments(max(rx, ry)) * 2), ry))


def ellipse_bottom(cx, cy, rx, ry):
    """Lower half of an ellipse, hanging from a flat top at ``cy``."""
    return _fan(cx, cy, _arc_points(cx, cy, rx, math.pi, 2 * math.pi, max(12, _segments(max(rx, ry)) * 2), ry))


def ear_on_ellipse(cx, cy, rx, ry, theta, spread, height):
    """Ear triangle sitting on an ellipse (a head): base around angle ``theta``
    (degrees) +- ``spread``, apex pushed out along the surface normal."""
    t, d = math.radians(theta), math.radians(spread)

    def on(a, inward=0.0):
        return (cx + rx * (1 - inward) * math.cos(a), cy + ry * (1 - inward) * math.sin(a))

    nx, ny = math.cos(t) / rx, math.sin(t) / ry
    length = math.hypot(nx, ny)
    mx, my = on(t)
    # Base sunk slightly into the head so no gap shows along the curve.
    return [on(t - d, 0.1), on(t + d, 0.1), (mx + nx / length * height, my + ny / length * height)]


def polygon(points):
    """Fan-triangulate a convex polygon."""
    tris = []
    for a, b in zip(points[1:], points[2:]):
        tris += [points[0], a, b]
    return tris


def strip(outer, inner):
    """Triangulate the band between two matching closed outlines."""
    tris = []
    n = len(outer)
    for i in range(n):
        j = (i + 1) % n
        tris += [outer[i], outer[j], inner[j], outer[i], inner[j], inner[i]]
    return tris


def rotated_rect(cx, cy, w, h, angle):
    c, s = math.cos(angle), math.sin(angle)
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return polygon([(cx + x * c - y * s, cy + x * s + y * c) for x, y in corners])


def rounded_rect(x0, y0, x1, y1, radius, corners=(True, True, True, True)):
    """Rectangle with rounded corners; ``corners`` = (top-left, top-right, bottom-right, bottom-left)."""
    rad = max(0.0, min(radius, (x1 - x0) / 2, (y1 - y0) / 2))
    if rad <= 0.0:
        return rect(x0, y0, x1, y1)
    tris = rect(x0 + rad, y0, x1 - rad, y1)
    tris += rect(x0, y0 + rad, x0 + rad, y1 - rad)
    tris += rect(x1 - rad, y0 + rad, x1, y1 - rad)
    half_pi = math.pi / 2
    for rounded, (cx, cy), a0, (sx0, sy0) in zip(
        corners,
        ((x0 + rad, y1 - rad), (x1 - rad, y1 - rad), (x1 - rad, y0 + rad), (x0 + rad, y0 + rad)),
        (half_pi, 0.0, -half_pi, math.pi),
        ((x0, y1 - rad), (x1 - rad, y1 - rad), (x1 - rad, y0), (x0, y0)),
    ):
        if rounded:
            tris += _fan(cx, cy, _arc_points(cx, cy, rad, a0, a0 + half_pi))
        else:
            tris += rect(sx0, sy0, sx0 + rad, sy0 + rad)
    return tris


def rounded_outline(x0, y0, x1, y1, radius, thickness):
    """A ring of ``thickness`` just inside a rounded rectangle's edge."""
    rad = max(thickness, min(radius, (x1 - x0) / 2, (y1 - y0) / 2))

    def outline(inset):
        pts = []
        for (cx, cy), a0 in zip(
            ((x1 - rad, y1 - rad), (x0 + rad, y1 - rad), (x0 + rad, y0 + rad), (x1 - rad, y0 + rad)),
            (0.0, math.pi / 2, math.pi, 3 * math.pi / 2),
        ):
            pts += _arc_points(cx, cy, rad - inset, a0, a0 + math.pi / 2, _segments(rad))
        return pts

    return strip(outline(0.0), outline(thickness))


def _xy(radius):
    """A corner radius as (rx, ry); a plain number is a circular corner."""
    return (radius, radius) if isinstance(radius, (int, float)) else radius


def radius_max(radii):
    return max(max(_xy(rad)) for rad in radii)


def rounded_points(x0, y0, x1, y1, radii, n=None):
    """Outline of a rounded rect with per-corner ``radii`` = (tl, tr, br, bl),
    with ``n + 1`` points per corner so two outlines can be ``strip``-ed.

    A radius may be a number or an (rx, ry) pair for an oval corner. The default
    ``n`` matches ``rounded_rect``'s arcs, so the outline lies exactly on that
    shape's edge.
    """
    tl, tr, br, bl = (_xy(rad) for rad in radii)
    if n is None:
        n = _segments(radius_max(radii))
    pts = []
    for (cx, cy), (rx, ry), a0 in (
        ((x1 - tr[0], y1 - tr[1]), tr, 0.0),
        ((x0 + tl[0], y1 - tl[1]), tl, math.pi / 2),
        ((x0 + bl[0], y0 + bl[1]), bl, math.pi),
        ((x1 - br[0], y0 + br[1]), br, 3 * math.pi / 2),
    ):
        pts += _arc_points(cx, cy, rx, a0, a0 + math.pi / 2, n, ry)
    return pts


def clip_tris(tris, a, b, c):
    """Keep the part of each triangle where a*x + b*y + c >= 0."""
    out = []
    for i in range(0, len(tris), 3):
        poly = tris[i:i + 3]
        kept = []
        for j, p in enumerate(poly):
            q = poly[(j + 1) % 3]
            fp, fq = a * p[0] + b * p[1] + c, a * q[0] + b * q[1] + c
            if fp >= 0:
                kept.append(p)
            if (fp >= 0) != (fq >= 0):
                t = fp / (fp - fq)
                kept.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
        if len(kept) >= 3 and _area(kept) > 1e-9:
            out += polygon(kept)
    return out


def _area(poly):
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def tube(p0, p1, p2, r0, r1, steps=None):
    """A smooth tapering tube along a quadratic Bezier (tails, legs): a strip
    between the two offset edges, with round caps at both ends."""
    if steps is None:
        length = math.dist(p0, p1) + math.dist(p1, p2)
        steps = max(12, min(64, math.ceil(length / (0.5 * max(min(r0, r1), 1e-6)))))
    left, right = [], []
    for i in range(steps + 1):
        t = i / steps
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        x = a * p0[0] + b * p1[0] + c * p2[0]
        y = a * p0[1] + b * p1[1] + c * p2[1]
        tx = 2 * (1 - t) * (p1[0] - p0[0]) + 2 * t * (p2[0] - p1[0])
        ty = 2 * (1 - t) * (p1[1] - p0[1]) + 2 * t * (p2[1] - p1[1])
        n = math.hypot(tx, ty)
        if n < 1e-9:  # control point on an end: fall back to the chord
            tx, ty, n = p2[0] - p0[0], p2[1] - p0[1], max(math.dist(p0, p2), 1e-9)
        rad = r0 + (r1 - r0) * t
        nx, ny = -ty / n * rad, tx / n * rad
        left.append((x + nx, y + ny))
        right.append((x - nx, y - ny))
    tris = []
    for i in range(steps):
        tris += [left[i], left[i + 1], right[i + 1], left[i], right[i + 1], right[i]]
    return tris + circle(*p0, r0, 16) + circle(*p2, r1, 16)


def offset(tris, dx, dy):
    return [(x + dx, y + dy) for x, y in tris]


def shrink(points, factor, dy=0.0):
    """Scale a polygon toward its centroid (inner ears)."""
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points) + dy
    return [(cx + (x - cx) * factor, cy + (y - cy) * factor) for x, y in points]


def shade(color, factor, alpha=1.0):
    return (color[0] * factor, color[1] * factor, color[2] * factor, alpha)


def mix(a, b, t, alpha=1.0):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t, alpha)


def clamp(v, lo, hi):
    return min(max(v, lo), hi)


# -- Cat Head --------------------------------------------------------------


def _cat_head(r, k):
    """Head bounds and corner radius; the rect corners stay inside because the
    corner radius never exceeds 3.41x the margin."""
    x0, y0, x1, y1 = r
    m = 16 * k
    X0, Y0, X1, Y1 = x0 - m, y0 - m, x1 + m, y1 + m
    R = min(3.3 * m, 0.5 * min(X1 - X0, Y1 - Y0))
    return (X0, Y0, X1, Y1), R


def _cat_ear_geometry(r, k):
    """Cat Head ears built like the Loaf/Tail ears (``_corner_ears``): they sit
    on the nearly flat part of the head, just inside its rounded corners, with
    the base a few units under the surface, about 1.15x as tall as wide, and the
    apex just inside the outer edge.

    Returns [(ear, visible)] where ``visible`` is the part above the head line,
    used to center the pink inner ear.
    """
    x0, y0, x1, y1 = r
    (X0, _Y0, X1, Y1), R = _cat_head(r, k)
    W = X1 - X0
    ear_h = clamp(0.4 * min(x1 - x0, y1 - y0), 30 * k, 70 * k)

    def surface(x):
        dx = max(X0 + R - x, x - (X1 - R), 0.0)  # distance into a corner's curve
        return Y1 - R + math.sqrt(max(R * R - dx * dx, 0.0))

    def at_height(p, q, y):
        t = (y - p[1]) / (q[1] - p[1])
        return (p[0] + (q[0] - p[0]) * t, y)

    ears = []
    for outer, side in ((X0 + min(0.75 * R, 0.12 * W), 1), (X1 - min(0.75 * R, 0.12 * W), -1)):
        base = surface(outer) - 5 * k
        bw = min((Y1 + ear_h - base) / 1.15, 0.3 * W)
        inner = outer + side * bw
        apex = (outer + side * 0.12 * bw, Y1 + ear_h)
        ear = [(outer, base), (inner, base), apex]
        seen = max(surface(outer), surface(inner))
        visible = [at_height(ear[0], apex, seen), at_height(ear[1], apex, seen), apex]
        ears.append((ear, visible))
    return ears


def _pink_down_to(tri, y):
    """Stretch a pink inner-ear triangle (two base corners, then apex) so its flat
    base sits at height ``y``, keeping the sides parallel to the ear's sides."""
    (b0, b1, apex) = tri

    def along(b):
        t = (apex[1] - y) / (apex[1] - b[1])
        return (apex[0] + (b[0] - apex[0]) * t, y)

    return [along(b0), along(b1), apex]


def _cat_ears(r, k):
    return [ear for ear, _visible in _cat_ear_geometry(r, k)]


def whisker_fan(sx, cy, k, color, side):
    """Three whiskers starting at (sx, cy), fanning out left (side=-1) or right (+1)."""
    whisker = shade(color, 0.45, 0.85)
    length, thickness = 30 * k, 1.6 * k
    layers = []
    for i, tilt in enumerate((-12, 0, 12)):
        ang = math.radians(tilt * side) + (math.pi if side < 0 else 0.0)
        ex = sx + math.cos(ang) * length / 2
        ey = cy + (i - 1) * 6 * k + math.sin(ang) * length / 2
        layers.append((rotated_rect(ex, ey, length, thickness, ang), whisker))
    return layers


def _whiskers(r, k, color):
    x0, y0, x1, y1 = r
    cy = y0 + 0.3 * (y1 - y0)
    return whisker_fan(x0 - 3 * k, cy, k, color, -1) + whisker_fan(x1 + 3 * k, cy, k, color, 1)


# -- Peeking Cat -----------------------------------------------------------


def _peek(r, k):
    """A black cat peeking over the top edge, with its rear end and tail hanging
    below the bottom edge. Returns a dict of the pieces."""
    x0, y0, x1, y1 = r
    w = x1 - x0
    hr = clamp(0.15 * w, 20 * k, 36 * k)
    cx = x0 + 0.7 * w
    cx = max(min(cx, x1 - 1.3 * hr), x0 + 1.3 * hr) if w > 2.6 * hr else (x0 + x1) / 2
    ears = [
        [(cx - 1.1 * hr, y1 + 0.35 * hr), (cx - 0.35 * hr, y1 + 0.85 * hr), (cx - 0.95 * hr, y1 + 1.45 * hr)],
        [(cx + 0.35 * hr, y1 + 0.85 * hr), (cx + 1.1 * hr, y1 + 0.35 * hr), (cx + 0.95 * hr, y1 + 1.45 * hr)],
    ]
    head = ellipse_top(cx, y1, 1.2 * hr, 0.95 * hr)
    for ear in ears:
        head += polygon(ear)
    # The rear end mirrors the head's arc below the note; the tail hangs from its middle.
    butt = ellipse_bottom(cx, y0, 1.2 * hr, 0.95 * hr)
    tail = tube((cx, y0 - 0.8 * hr), (cx + 0.05 * hr, y0 - 1.9 * hr), (cx + 1.0 * hr, y0 - 2.45 * hr),
                0.22 * hr, 0.15 * hr)
    return {"cx": cx, "hr": hr, "ears": ears, "head": head, "butt": butt, "tail": tail, "star_y": y0 - 0.72 * hr}


def _peek_over(r, k):
    _x0, y0, _x1, y1 = r
    p = _peek(r, k)
    cx, hr = p["cx"], p["hr"]
    line = mix(FUR, WHITE, 0.25)

    def toe_lines(px, top, bottom):
        return [(rect(px + t * hr - 0.6 * k, bottom, px + t * hr + 0.6 * k, top), line) for t in (-0.1, 0.1)]

    # The head, rear end and tail are drawn *behind* the note (see ``under``);
    # only the features and the front paws are drawn in front of it.
    # A little pink asterisk at the base of the rear arc, just above the tail:
    layers = []
    star_len, star_w = 0.2 * hr, max(0.045 * hr, 1.0)
    for ang in (90, 30, 150):
        layers.append((rotated_rect(cx, p["star_y"], star_len, star_w, math.radians(ang)), mix(FUR, PINK, 0.6)))

    for ear in p["ears"]:
        layers.append((polygon(shrink(ear, 0.5, -0.05 * hr)), mix(FUR, PINK, 0.6)))
    for side in (-1, 1):
        ex, ey = cx + side * 0.42 * hr, y1 + 0.42 * hr
        layers += [
            (ellipse(ex, ey, 0.17 * hr, 0.2 * hr), (*EYE, 1.0)),
            (ellipse(ex, ey, 0.06 * hr, 0.16 * hr), (*PUPIL, 1.0)),
            (circle(ex + 0.06 * hr, ey + 0.08 * hr, 0.05 * hr, 12), (*WHITE, 0.9)),
        ]
    layers.append((polygon([(cx - 0.09 * hr, y1 + 0.24 * hr), (cx + 0.09 * hr, y1 + 0.24 * hr), (cx, y1 + 0.13 * hr)]), (*PINK, 1.0)))
    # Front paws gripping the top edge.
    for side in (-1, 1):
        px = cx + side * 0.62 * hr
        layers.append((ellipse(px, y1, 0.3 * hr, 0.22 * hr), (*FUR, 1.0)))
        layers += toe_lines(px, y1 - 0.02 * hr, y1 - 0.18 * hr)
    return layers


# -- Paw Print -------------------------------------------------------------

CLAW = (0.97, 0.94, 0.88)
PAD_INSET = 4.0  # note units: the pink pad sits this far inside the frame, leaving a fur rim


def _paw(r, k):
    """Pad bounds/radius, toe circles (cx, cy, radius) and claw triangles."""
    x0, y0, x1, y1 = r
    m = 10 * k
    X0, Y0, X1, Y1 = x0 - m, y0 - m, x1 + m, y1 + m
    R = min(3.3 * m, 0.5 * min(X1 - X0, Y1 - Y0))
    W = X1 - X0
    tr = clamp(0.1 * W, 11 * k, 24 * k)
    toes = [
        (X0 + 0.15 * W, Y1 + 0.15 * tr, tr),
        (X0 + 0.38 * W, Y1 + 0.6 * tr, tr),
        (X0 + 0.62 * W, Y1 + 0.6 * tr, tr),
        (X0 + 0.85 * W, Y1 + 0.15 * tr, tr),
    ]
    # Claws point straight up; their bases hide behind the toe fur.
    claws = [[(cx - 0.32 * t, cy + 0.5 * t), (cx + 0.32 * t, cy + 0.5 * t), (cx, cy + 1.55 * t)] for cx, cy, t in toes]
    return {"bounds": (X0, Y0, X1, Y1), "R": R, "toes": toes, "claws": claws}


def _paw_pad(r, k):
    x0, y0, x1, y1 = r
    i = PAD_INSET * k
    return rounded_rect(x0 + i, y0 + i, x1 - i, y1 - i, 10 * k)


# -- Cat Loaf --------------------------------------------------------------


def _corner_ears(X0, Y1, W, H, k):
    """Two big ears on a head's top-left corner, leaning outward."""
    ear_h = clamp(0.42 * H, 24 * k, 46 * k)
    bw = min(clamp(0.14 * W, 22 * k, 46 * k), 0.19 * W)  # small notes keep both ears on the head
    base = Y1 - 7 * k
    return [
        [(X0 + 5 * k, base), (X0 + 5 * k + bw, base), (X0 + 5 * k + 0.12 * bw, Y1 + ear_h)],
        [(X0 + 9 * k + 1.15 * bw, base), (X0 + 9 * k + 2.15 * bw, base), (X0 + 9 * k + 2.0 * bw, Y1 + 0.95 * ear_h)],
    ]


def j_tail(X1, Y0, k, reach, rise, thickness=7.0):
    """A tail whose bottom edge carries straight on from the belly line, then
    turns up the back of the cat and curls over at the tip."""
    tr = thickness * k
    turn = (X1 + reach, Y0 + tr + reach)
    tail = tube((X1 - 12 * k, Y0 + tr), (X1 + reach, Y0 + tr), turn, tr, 0.92 * tr)
    tail += tube(turn, (X1 + reach, Y0 + rise), (X1 + reach - 9 * k, Y0 + rise + 7 * k), 0.92 * tr, 0.85 * tr)
    return tail


def _loaf(r, k):
    """A loaf cat seen from the side, facing left. The body's left end is the
    head (big ears on its top corner, whiskers, paws tucked under the chin);
    the rump's corner matches the head's; the belly runs straight on into a
    tail that curls up the back.

    Every body corner contains the frame corner: R <= m1 + m2 + sqrt(2 m1 m2).
    """
    x0, y0, x1, y1 = r
    ml, mt, mr, mb = 14 * k, 10 * k, 12 * k, 10 * k
    X0, Y0, X1, Y1 = x0 - ml, y0 - mb, x1 + mr, y1 + mt
    W, H = X1 - X0, Y1 - Y0
    corner = min(16 * k, H / 2)
    radii = (corner, corner, min(8 * k, H / 2), min(22 * k, H / 2))
    body = polygon(rounded_points(X0, Y0, X1, Y1, radii))
    tail = j_tail(X1, Y0, k, reach=20 * k, rise=clamp(0.7 * H, 30 * k, 60 * k))
    paws = [(X0 + f * W, Y0 + 1 * k) for f in (0.1, 0.22)]
    return {
        "body": body, "ears": _corner_ears(X0, Y1, W, H, k), "tail": tail, "paws": paws,
        "outline": (X0, Y0, X1, Y1, radii), "face": (X0 + 4 * k, Y0 + 0.45 * H),
    }


# -- Kitty Tail ------------------------------------------------------------


ELBOW_R = 11.0  # note units


def _kitty(r, k):
    """A stretched-out cat facing left, built like the Loaf, with a slim front
    leg angling down-left from the chin to a paw (the speech-bubble pointer),
    a little elbow bump just behind the arm, and a tall tail rising above
    its back."""
    x0, y0, x1, y1 = r
    ml, mt, mr, mb = 14 * k, 10 * k, 12 * k, 10 * k
    X0, Y0, X1, Y1 = x0 - ml, y0 - mb, x1 + mr, y1 + mt
    W, H = X1 - X0, Y1 - Y0
    corner = min(16 * k, H / 2)
    radii = (corner, corner, min(8 * k, H / 2), corner)
    # Slim leg: the outer edge carries on from the face wall, the inner edge leaves
    # the belly a short way along; both taper down-left to a round paw.
    aw = clamp(0.45 * H, 22 * k, 40 * k)
    pr = 8 * k
    paw = (X0 - 6 * k, Y0 - clamp(1.0 * H, 45 * k, 75 * k))
    # Starting on the left wall above the chin's curve fills the whole corner, so
    # the arm meets the body with no gap.
    leg = polygon([(X0, Y0 + corner), (X0 + aw, Y0 + 2 * k), (paw[0] + pr, paw[1] + 0.4 * pr), (paw[0] - pr, paw[1] + 0.4 * pr)])
    leg += circle(paw[0], paw[1], 1.1 * pr)
    leg += circle(X0 + 2.1 * aw, Y0 - 2 * k, ELBOW_R * k)  # elbow paw, just past where the arm meets the belly
    tail = j_tail(X1, Y0, k, reach=22 * k, rise=H + 18 * k)
    return {
        "outline": (X0, Y0, X1, Y1, radii), "ears": _corner_ears(X0, Y1, W, H, k), "leg": leg, "paw": paw,
        "tail": tail, "face": (X0 + 4 * k, Y0 + 0.55 * H),
    }


# -- style dispatch --------------------------------------------------------


def parts(style, r, k, radius):
    """(body, silhouette_extras) for a style.

    ``body`` is painted in the note color under the frame. ``silhouette_extras``
    are shapes drawn later in other colors that still cast a shadow and get the
    selection halo.
    """
    if style == "PEEK":
        p = _peek(r, k)
        return rounded_rect(*r, radius), p["head"] + p["butt"] + p["tail"]
    if style == "PAW":
        p = _paw(r, k)
        body = rounded_rect(*p["bounds"], p["R"])
        for cx, cy, tr in p["toes"]:
            body += circle(cx, cy, tr)
        claws = []
        for claw in p["claws"]:
            claws += polygon(claw)
        return body, claws
    if style == "LOAF":
        p = _loaf(r, k)
        body = p["body"] + p["tail"]
        for ear in p["ears"]:
            body += polygon(ear)
        return body, []
    if style == "TAIL":
        p = _kitty(r, k)
        body = polygon(rounded_points(*p["outline"])) + p["leg"] + p["tail"]
        for ear in p["ears"]:
            body += polygon(ear)
        return body, []
    # CAT, and unknown styles from older versions.
    (X0, Y0, X1, Y1), R = _cat_head(r, k)
    body = rounded_rect(X0, Y0, X1, Y1, R)
    for ear in _cat_ears(r, k):
        body += polygon(ear)
    return body, []


def silhouette(style, r, k, radius):
    body, extras = parts(style, r, k, radius)
    return body + extras


def halo(tris, width):
    """Grow a silhouette by ``width``: the union of eight offset copies."""
    out = []
    for dx, dy in _EIGHT_WAYS:
        out += offset(tris, dx * width, dy * width)
    return out


# Soft drop shadow: (dx, dy, alpha) per layer, in note units.
SHADOW_LAYERS = ((3.0, -6.0, 0.10), (2.0, -4.0, 0.12), (1.0, -2.0, 0.14))


def under(style, r, k, color, radius, halo_color=None, shadow=True):
    """Layers drawn beneath the frame: shadow, selection halo, then the body.

    The silhouette is a union of overlapping pieces, so translucent shadow
    layers built from it darken wherever pieces overlap. ``draw`` therefore
    renders the shadow once from an off-screen mask and passes ``shadow=False``;
    the per-piece layers here are its fallback.
    """
    body, extras = parts(style, r, k, radius)
    sil = body + extras
    layers = []
    if shadow:
        layers += [(offset(sil, dx * k, dy * k), (*SHADOW, a)) for dx, dy, a in SHADOW_LAYERS]
    if halo_color is not None:
        layers.append((halo(sil, max(2.5 * k, 1.5)), halo_color))
    if style == "PAW":  # claws peek out from behind the toes
        layers += [(polygon(claw), (*CLAW, 1.0)) for claw in _paw(r, k)["claws"]]
    elif style == "PEEK":  # the cat sits behind the note; only its front paws come over the edge
        p = _peek(r, k)
        layers += [(p["tail"], (*FUR, 1.0)), (p["butt"], (*FUR, 1.0)), (p["head"], (*FUR, 1.0))]
    layers.append((body, (*color, 1.0)))
    return layers


def text_backdrop(style, color):
    """The color directly behind the text (for picking a readable text color)."""
    if style == "PAW":
        return mix(color, PINK, 0.6)[:3]
    return tuple(color[:3])


COVER_INSET = 1.5  # note units inside the frame edge, enough to hide Blender's frame outline


def _body_outline(style, r, k):
    """The main body's rounded rect as (x0, y0, x1, y1, radii), or None when the
    body is the frame rectangle itself (PEEK)."""
    if style == "PEEK":
        return None
    if style == "PAW":
        p = _paw(r, k)
        return (*p["bounds"], (p["R"],) * 4)
    if style == "LOAF":
        return _loaf(r, k)["outline"]
    if style == "TAIL":
        return _kitty(r, k)["outline"]
    (X0, Y0, X1, Y1), R = _cat_head(r, k)
    return X0, Y0, X1, Y1, (R,) * 4


def margin_cover(style, r, k, radius, min_inset=0.0, top_inset=0.0):
    """Everything of the cat body that lies outside the frame rectangle, plus a
    sliver just inside its edge.

    Painted on top in the note color, it hides Blender's own frame outline,
    drop shadow and rectangular selection outline wherever they fall on the
    shape, at any zoom, while leaving the frame interior (and any nodes on it)
    untouched.

    Blender draws its outline at a fixed on-screen width, a few pixels inside
    the edge, so ``min_inset`` (pixels) keeps it covered when zoomed out. Text
    is drawn after the cover, so a deeper inset never hides text.

    ``top_inset`` extends the cover over the name strip at the top, hiding
    Blender's own label there (the add-on draws the name itself).
    """
    x0, y0, x1, y1 = r
    inset = min(max(COVER_INSET * k, min_inset, 1.0), 0.25 * min(x1 - x0, y1 - y0))
    top = min(max(inset, top_inset), (y1 - y0) - inset - 1.0)
    outline = _body_outline(style, r, k)
    if outline is None:
        o = max(1.0 * k, 1.0)  # thin ring over the edge; keeps the selection halo visible
        outline = (x0 - o, y0 - o, x1 + o, y1 + o, (radius + o,) * 4)
    n = _segments(radius_max(outline[4]))
    outer = rounded_points(*outline, n=n)
    inner = rounded_points(x0 + inset, y0 + inset, x1 - inset, y1 - top, (max(radius - inset, 0.0),) * 4, n=n)
    tris = strip(outer, inner)
    # Tails and legs start inside the frame; the frame's shadow falls on their base.
    if style == "LOAF":
        tris += clip_tris(_loaf(r, k)["tail"], 1.0, 0.0, -x1)
    elif style == "TAIL":
        p = _kitty(r, k)
        tris += clip_tris(p["tail"], 1.0, 0.0, -x1)
        tris += clip_tris(p["leg"], 0.0, -1.0, y0)
    return tris


def over(style, r, k, color, radius):
    if style == "PEEK":
        return _peek_over(r, k)
    if style == "PAW":
        p = _paw(r, k)
        bean = mix(color, PINK, 0.6)
        layers = [(circle(cx, cy - 0.1 * tr, 0.55 * tr), bean) for cx, cy, tr in p["toes"]]
        layers.append((_paw_pad(r, k), bean))  # the pink pad is the text window
        return layers
    if style == "LOAF":
        p = _loaf(r, k)
        layers = [(polygon(shrink(ear, 0.5, -1 * k)), mix(color, PINK, 0.55)) for ear in p["ears"]]
        for px, py in p["paws"]:
            layers.append((ellipse(px, py, 9 * k, 6 * k), mix(color, WHITE, 0.45)))
        return layers + whisker_fan(*p["face"], k, color, -1)
    if style == "TAIL":
        p = _kitty(r, k)
        layers = [(polygon(shrink(ear, 0.5, -1 * k)), mix(color, PINK, 0.55)) for ear in p["ears"]]
        # Toe lines on the hanging paw.
        px, py = p["paw"]
        for t in (-3.0, 3.0):
            layers.append((rect(px + t * k - 0.6 * k, py - 9 * k, px + t * k + 0.6 * k, py - 4 * k), shade(color, 0.7)))
        return layers + whisker_fan(*p["face"], k, color, -1)
    # CAT, and unknown styles from older versions.
    # Pink inner ears centered on the visible part of each ear, their bottom edge
    # running flat along the head line, as on the Loaf/Tail.
    layers = [(polygon(_pink_down_to(shrink(visible, 0.5, -1 * k), visible[0][1] + 1 * k)), mix(color, PINK, 0.55))
              for _ear, visible in _cat_ear_geometry(r, k)]
    return layers + _whiskers(r, k, color)
