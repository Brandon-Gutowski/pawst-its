"""Geometry for the note styles, as lists of (triangles, rgba) to fill.

All functions take the note rectangle ``r = (x0, y0, x1, y1)`` (y up) in the
current drawing space and ``k``, the size of one note unit in that space, so
the same code serves both the view-space and the pixel-space passes.

``under()`` is drawn beneath the native Frame node (which is 80% opaque), so it
supplies the solid body and anything that sticks out of the rectangle.
``over()`` is drawn on top of everything.
"""

import math

SHADOW = (0.0, 0.0, 0.0)


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y0), (x1, y1), (x0, y1)]


def circle(cx, cy, radius, segments=None):
    if segments is None:
        segments = max(12, min(64, int(radius * 0.8)))
    pts = [
        (cx + radius * math.cos(2 * math.pi * i / segments), cy + radius * math.sin(2 * math.pi * i / segments))
        for i in range(segments + 1)
    ]
    tris = []
    for a, b in zip(pts, pts[1:]):
        tris += [(cx, cy), a, b]
    return tris


def polygon(points):
    """Fan-triangulate a convex polygon."""
    tris = []
    for a, b in zip(points[1:], points[2:]):
        tris += [points[0], a, b]
    return tris


def rotated_rect(cx, cy, w, h, angle):
    c, s = math.cos(angle), math.sin(angle)
    corners = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    return polygon([(cx + x * c - y * s, cy + x * s + y * c) for x, y in corners])


def offset(tris, dx, dy):
    return [(x + dx, y + dy) for x, y in tris]


def shade(color, factor, alpha=1.0):
    return (color[0] * factor, color[1] * factor, color[2] * factor, alpha)


# -- silhouettes -----------------------------------------------------------


def _cloud_bumps(r, k):
    x0, y0, x1, y1 = r
    radius = 13 * k
    step = 1.45 * radius
    tris = []

    def edge(ax, ay, bx, by):
        n = max(1, round(math.hypot(bx - ax, by - ay) / step))
        for i in range(n + 1):
            t = i / n
            tris.extend(circle(ax + (bx - ax) * t, ay + (by - ay) * t, radius))

    inset = radius * 0.35
    edge(x0 + inset, y1, x1 - inset, y1)
    edge(x0 + inset, y0, x1 - inset, y0)
    edge(x0, y0 + inset, x0, y1 - inset)
    edge(x1, y0 + inset, x1, y1 - inset)
    # Thought trail drifting off the bottom-left.
    tris += circle(x0 - 6 * k, y0 - 24 * k, 8 * k)
    tris += circle(x0 - 19 * k, y0 - 40 * k, 5.5 * k)
    tris += circle(x0 - 28 * k, y0 - 52 * k, 3.5 * k)
    return tris


def _bubble_tail(r, k):
    x0, y0, _x1, _y1 = r
    return polygon([(x0 + 24 * k, y0 + k), (x0 + 58 * k, y0 + k), (x0 + 10 * k, y0 - 34 * k)])


def silhouette(style, r, k):
    tris = rect(*r)
    if style == "CLOUD":
        tris += _cloud_bumps(r, k)
    elif style == "BUBBLE":
        tris += _bubble_tail(r, k)
    return tris


# -- layers ----------------------------------------------------------------


def under(style, r, k, color):
    body = silhouette(style, r, k)
    layers = [
        (offset(body, 3.0 * k, -6.0 * k), (*SHADOW, 0.10)),
        (offset(body, 2.0 * k, -4.0 * k), (*SHADOW, 0.12)),
        (offset(body, 1.0 * k, -2.0 * k), (*SHADOW, 0.14)),
        (body, (*color, 1.0)),
    ]
    return layers


def over(style, r, k, color, background):
    x0, y0, x1, y1 = r
    w, h = x1 - x0, y1 - y0
    layers = []

    if style == "CLASSIC":
        layers.append((rect(x0, y1 - 7 * k, x1, y1), (*SHADOW, 0.08)))

    elif style == "PUSHPIN":
        cx, cy = (x0 + x1) / 2, y1 - 6 * k
        layers += [
            (circle(cx + 3 * k, cy - 4 * k, 10 * k), (*SHADOW, 0.25)),
            (circle(cx, cy, 10 * k), (0.80, 0.16, 0.22, 1.0)),
            (circle(cx - 0.8 * k, cy + 0.8 * k, 7.5 * k), (0.95, 0.30, 0.36, 1.0)),
            (circle(cx - 3.2 * k, cy + 3.2 * k, 2.6 * k), (1.0, 1.0, 1.0, 0.75)),
        ]

    elif style == "TAPE":
        tape_w, tape_h = 64 * k, 20 * k
        for cx, ang in ((x0 + 6 * k, math.radians(40)), (x1 - 6 * k, math.radians(-40))):
            cy = y1 - 4 * k
            layers.append((rotated_rect(cx, cy, tape_w, tape_h, ang), (1.0, 1.0, 1.0, 0.45)))
            # Washi stripes along the strip.
            for off in (-0.25, 0.25):
                dx, dy = -math.sin(ang) * off * tape_h, math.cos(ang) * off * tape_h
                layers.append(
                    (rotated_rect(cx + dx, cy + dy, tape_w, 2.2 * k, ang), shade(color, 0.75, 0.55))
                )

    elif style == "DOGEAR":
        f = min(30 * k, 0.35 * min(w, h))
        layers += [
            (polygon([(x1 - f, y0), (x1, y0), (x1, y0 + f)]), (*background, 1.0)),
            (polygon([(x1 - f, y0), (x1, y0 + f), (x1 - f - 2 * k, y0 + f + 2 * k)]), (*SHADOW, 0.18)),
            (polygon([(x1 - f, y0), (x1, y0 + f), (x1 - f, y0 + f)]), shade(color, 0.82)),
        ]

    return layers
