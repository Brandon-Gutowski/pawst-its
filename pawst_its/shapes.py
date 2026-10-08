"""Geometry for the cat styles, as lists of (triangles, rgba) to fill.

All functions take the note rectangle ``r = (x0, y0, x1, y1)`` (y up) in the
current drawing space and ``k``, the size of one note unit in that space, so
the same code serves any zoom level. ``radius`` is the native Frame's corner
radius in that space.

``under()`` is drawn beneath the native Frame node, which is 80% opaque in the
note's own color. Wherever a body covers the frame's rounded rectangle the
frame blends in invisibly, so every body must either match that rounded
rectangle exactly or fully contain it.
``over()`` is drawn on top of everything.
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


def rounded_points(x0, y0, x1, y1, radii, n=None):
    """Outline of a rounded rect with per-corner ``radii`` = (tl, tr, br, bl),
    with ``n + 1`` points per corner so two outlines can be ``strip``-ed.

    The default ``n`` matches ``rounded_rect``'s arcs, so the outline lies
    exactly on that shape's edge.
    """
    tl, tr, br, bl = radii
    if n is None:
        n = _segments(max(radii))
    pts = []
    for (cx, cy), rad, a0 in (
        ((x1 - tr, y1 - tr), tr, 0.0),
        ((x0 + tl, y1 - tl), tl, math.pi / 2),
        ((x0 + bl, y0 + bl), bl, math.pi),
        ((x1 - br, y0 + br), br, 3 * math.pi / 2),
    ):
        pts += _arc_points(cx, cy, rad, a0, a0 + math.pi / 2, n)
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
        out += polygon(kept) if len(kept) >= 3 else []
    return out


def tube(p0, p1, p2, r0, r1, steps=18):
    """Chain of tapering circles along a quadratic Bezier (fluffy tails)."""
    tris = []
    for i in range(steps + 1):
        t = i / steps
        a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
        x = a * p0[0] + b * p1[0] + c * p2[0]
        y = a * p0[1] + b * p1[1] + c * p2[1]
        tris += circle(x, y, r0 + (r1 - r0) * t, 16)
    return tris


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


def _cat_ears(r, k):
    x0, y0, x1, y1 = r
    (X0, _Y0, X1, Y1), R = _cat_head(r, k)
    W = X1 - X0
    ear_h = clamp(0.4 * min(x1 - x0, y1 - y0), 30 * k, 70 * k)
    base_w = min(0.3 * W, 1.4 * ear_h)
    base_y = Y1 - 0.5 * R
    left = [(X0 + 0.08 * W, base_y), (X0 + 0.08 * W + base_w, base_y), (X0 + 0.08 * W + 0.12 * base_w, Y1 + ear_h)]
    right = [(X1 - 0.08 * W - base_w, base_y), (X1 - 0.08 * W, base_y), (X1 - 0.08 * W - 0.12 * base_w, Y1 + ear_h)]
    return [left, right]


def _whiskers(r, k, color):
    x0, y0, x1, y1 = r
    layers = []
    whisker = shade(color, 0.45, 0.85)
    length, thickness = 30 * k, 1.6 * k
    cy = y0 + 0.3 * (y1 - y0)
    for side, sx in ((-1, x0 - 3 * k), (1, x1 + 3 * k)):
        for i, tilt in enumerate((-12, 0, 12)):
            ang = math.radians(tilt * side) + (math.pi if side < 0 else 0.0)
            ex = sx + math.cos(ang) * length / 2
            ey = cy + (i - 1) * 6 * k + math.sin(ang) * length / 2
            layers.append((rotated_rect(ex, ey, length, thickness, ang), whisker))
    return layers


# -- Peeking Cat -----------------------------------------------------------


def _peek(r, k):
    """Center x, head radius, head+ears outline for the cat peeking over the top."""
    x0, _y0, x1, y1 = r
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
    return cx, hr, head, ears


def _peek_over(r, k):
    _x0, _y0, _x1, y1 = r
    cx, hr, head, ears = _peek(r, k)
    layers = [(head, (*FUR, 1.0))]
    for ear in ears:
        layers.append((polygon(shrink(ear, 0.5, -0.05 * hr)), mix(FUR, PINK, 0.6)))
    for side in (-1, 1):
        ex, ey = cx + side * 0.42 * hr, y1 + 0.42 * hr
        layers += [
            (ellipse(ex, ey, 0.17 * hr, 0.2 * hr), (*EYE, 1.0)),
            (ellipse(ex, ey, 0.06 * hr, 0.16 * hr), (*PUPIL, 1.0)),
            (circle(ex + 0.06 * hr, ey + 0.08 * hr, 0.05 * hr, 12), (*WHITE, 0.9)),
        ]
    layers.append((polygon([(cx - 0.09 * hr, y1 + 0.24 * hr), (cx + 0.09 * hr, y1 + 0.24 * hr), (cx, y1 + 0.13 * hr)]), (*PINK, 1.0)))
    # Paws gripping the top edge.
    for side in (-1, 1):
        px = cx + side * 0.62 * hr
        layers.append((ellipse(px, y1, 0.3 * hr, 0.22 * hr), (*FUR, 1.0)))
        for t in (-0.1, 0.1):
            layers.append((rect(px + t * hr - 0.6 * k, y1 - 0.18 * hr, px + t * hr + 0.6 * k, y1 - 0.02 * hr), mix(FUR, WHITE, 0.25)))
    return layers


# -- Paw Print -------------------------------------------------------------


def _paw(r, k):
    """Pad bounds/radius and toe circles (cx, cy, radius)."""
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
    return (X0, Y0, X1, Y1), R, toes


# -- Cat Loaf --------------------------------------------------------------


def _loaf(r, k):
    """Loaf body (a rounded rect with a big domed top) plus ears and tail.

    Dome corners contain the rect while R <= m_side + m_top + sqrt(2 m_side m_top).
    """
    x0, y0, x1, y1 = r
    ms, mt, mb = 12 * k, 26 * k, 10 * k
    X0, Y0, X1, Y1 = x0 - ms, y0 - mb, x1 + ms, y1 + mt
    W = X1 - X0
    rb = 8 * k
    rr = min(56 * k, 0.5 * W, Y1 - Y0 - rb)
    radii = (rr, rr, rb, rb)
    body = polygon(rounded_points(X0, Y0, X1, Y1, radii))

    def surface(x):
        if x < X0 + rr:
            return Y1 - rr + math.sqrt(max(0.0, rr * rr - (X0 + rr - x) ** 2))
        if x > X1 - rr:
            return Y1 - rr + math.sqrt(max(0.0, rr * rr - (x - (X1 - rr)) ** 2))
        return Y1

    ear_h = clamp(0.32 * min(x1 - x0, y1 - y0), 22 * k, 40 * k)
    bw = clamp(0.2 * W, 26 * k, 50 * k)
    ears = []
    for b0 in (X0 + 0.2 * W, X1 - 0.2 * W - bw):
        b1 = b0 + bw
        base = min(surface(b0), surface(b1)) - 4 * k
        top = max(surface(b0), surface(b1)) + ear_h
        apex_x = b0 + 0.25 * bw if b0 < (X0 + X1) / 2 else b1 - 0.25 * bw
        ears.append([(b0, base), (b1, base), (apex_x, top)])
    tail = tube((X1 - 6 * k, Y0 + 6 * k), (X1 + 34 * k, Y0 - 6 * k), (X1 + 22 * k, Y0 + 30 * k), 7 * k, 4.5 * k)
    return body, ears, tail, (X0, Y0, X1, Y1, radii)


# -- Kitty Tail ------------------------------------------------------------


def _kitty(r, k):
    x0, y0, x1, y1 = r
    s = min(1.0, (x1 - x0) / (90 * k))
    ears = [
        [(x0 + 10 * k * s, y1 - 3 * k), (x0 + 34 * k * s, y1 - 3 * k), (x0 + 14 * k * s, y1 + 22 * k * s)],
        [(x0 + 40 * k * s, y1 - 3 * k), (x0 + 64 * k * s, y1 - 3 * k), (x0 + 60 * k * s, y1 + 22 * k * s)],
    ]
    mid = (x1 + 34 * k, y0 + 40 * k)
    tail = tube((x1 - 4 * k, y0 + 12 * k), (x1 + 44 * k, y0 + 4 * k), mid, 8 * k, 6 * k)
    tail += tube(mid, (x1 + 26 * k, y0 + 70 * k), (x1 + 44 * k, y0 + 78 * k), 6 * k, 7 * k)
    tip = (x1 + 44 * k, y0 + 78 * k)
    return ears, tail, tip


# -- style dispatch --------------------------------------------------------


def parts(style, r, k, radius):
    """(body, silhouette_extras) for a style.

    ``body`` is painted in the note color under the frame. ``silhouette_extras``
    are shapes drawn later in other colors that still cast a shadow and get the
    selection halo.
    """
    if style == "PEEK":
        _cx, _hr, head, _ears = _peek(r, k)
        return rounded_rect(*r, radius), head
    if style == "PAW":
        (X0, Y0, X1, Y1), R, toes = _paw(r, k)
        body = rounded_rect(X0, Y0, X1, Y1, R)
        for cx, cy, tr in toes:
            body += circle(cx, cy, tr)
        return body, []
    if style == "LOAF":
        body, ears, tail, _b = _loaf(r, k)
        for ear in ears:
            body += polygon(ear)
        return body + tail, []
    if style == "TAIL":
        ears, tail, _tip = _kitty(r, k)
        body = rounded_rect(*r, radius) + tail
        for ear in ears:
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


def under(style, r, k, color, radius, halo_color=None):
    body, extras = parts(style, r, k, radius)
    sil = body + extras
    layers = [
        (offset(sil, 3.0 * k, -6.0 * k), (*SHADOW, 0.10)),
        (offset(sil, 2.0 * k, -4.0 * k), (*SHADOW, 0.12)),
        (offset(sil, 1.0 * k, -2.0 * k), (*SHADOW, 0.14)),
    ]
    if halo_color is not None:
        layers.append((halo(sil, max(2.5 * k, 1.5)), halo_color))
    layers.append((body, (*color, 1.0)))
    return layers


COVER_INSET = 1.5  # note units inside the frame edge, enough to hide Blender's frame outline


def _body_outline(style, r, k):
    """The main body's rounded rect as (x0, y0, x1, y1, radii), or None when the
    body is the frame rectangle itself (PEEK, TAIL)."""
    if style in ("PEEK", "TAIL"):
        return None
    if style == "PAW":
        (X0, Y0, X1, Y1), R, _toes = _paw(r, k)
        return X0, Y0, X1, Y1, (R,) * 4
    if style == "LOAF":
        _body, _ears, _tail, outline = _loaf(r, k)
        return outline
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
    n = _segments(max(outline[4]))
    outer = rounded_points(*outline, n=n)
    inner = rounded_points(x0 + inset, y0 + inset, x1 - inset, y1 - top, (max(radius - inset, 0.0),) * 4, n=n)
    tris = strip(outer, inner)
    # Tails start inside the frame; the frame's shadow falls on their base.
    if style == "LOAF":
        tris += clip_tris(_loaf(r, k)[2], 1.0, 0.0, -x1)
    elif style == "TAIL":
        tris += clip_tris(_kitty(r, k)[1], 1.0, 0.0, -x1)
    return tris


def over(style, r, k, color, radius):
    if style == "PEEK":
        return _peek_over(r, k)
    if style == "PAW":
        _b, _R, toes = _paw(r, k)
        return [(circle(cx, cy - 0.1 * tr, 0.55 * tr), mix(color, PINK, 0.6)) for cx, cy, tr in toes]
    if style == "LOAF":
        _body, ears, _tail, (X0, Y0, _X1, _Y1, _radii) = _loaf(r, k)
        x0, _y0, x1, _y1 = r
        layers = [(polygon(shrink(ear, 0.5, -2 * k)), mix(color, PINK, 0.55)) for ear in ears]
        # Little front paws tucked under the loaf.
        for fx in (0.16, 0.3):
            layers.append((ellipse(x0 + fx * (x1 - x0), Y0 + 1 * k, 9 * k, 6 * k), mix(color, WHITE, 0.45)))
        return layers
    if style == "TAIL":
        ears, _tail, tip = _kitty(r, k)
        layers = [(polygon(shrink(ear, 0.5, -2 * k)), mix(color, PINK, 0.55)) for ear in ears]
        layers.append((circle(tip[0], tip[1], 6.5 * k), shade(color, 0.82)))
        return layers
    # CAT, and unknown styles from older versions.
    layers = [(polygon(shrink(ear, 0.55, 0.12 * (ear[2][1] - ear[0][1]))), mix(color, PINK, 0.55)) for ear in _cat_ears(r, k)]
    return layers + _whiskers(r, k, color)
