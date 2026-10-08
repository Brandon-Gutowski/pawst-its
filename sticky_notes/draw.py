"""Drawing of sticky notes in every node editor, plus layout/geometry helpers."""

import blf
import bpy
import gpu
from gpu_extras.batch import batch_for_shader

from . import shapes
from .props import is_note, note_body
from .text_layout import line_index, wrap

FONT = 0
PAD = 10.0  # note units between frame edge and text
LINE_SPACING = 1.3
REF_SIZE = 64.0  # font size used for measuring; widths are scaled linearly from it
MIN_TEXT_PX = 3.0

# Set by the edit operator while a note is being typed into.
editing = None


class EditState:
    def __init__(self, tree, node_name, buffer):
        self.tree_ptr = tree.as_pointer()
        self.node_name = node_name
        self.buffer = buffer
        self.caret_visible = True

    def matches(self, tree, node):
        return tree.as_pointer() == self.tree_ptr and node.name == self.node_name


# -- geometry --------------------------------------------------------------


_measured_scale = None


def ui_scale():
    """Blender's UI_SCALE_FAC: node units -> view units.

    Measured from a drawn frame when possible (exact), else estimated from the
    integer DPI preference.
    """
    if _measured_scale is not None:
        return _measured_scale
    return bpy.context.preferences.system.dpi / 72.0


def _measure_scale(notes):
    global _measured_scale
    for node in notes:
        if node.width > 1.0 and node.dimensions[0] > 1.0:
            _measured_scale = node.dimensions[0] / node.width
            return


def node_location(node):
    loc = getattr(node, "location_absolute", None)  # Blender 4.4+
    if loc is not None:
        return loc[0], loc[1]
    x, y = node.location
    parent = node.parent
    while parent is not None:
        x += parent.location[0]
        y += parent.location[1]
        parent = parent.parent
    return x, y


def note_rect_view(node, scale):
    """Note rectangle (x0, y0, x1, y1) in view space."""
    x, y = node_location(node)
    x0, y1 = x * scale, y * scale
    return x0, y1 - node.height * scale, x0 + node.width * scale, y1


# Styles whose decorations sit over the top edge need room above the text.
_DECORATED_TOP = {"PUSHPIN": 22.0, "TAPE": 20.0}


def header_height(node):
    """Space at the top reserved for the frame's native label (the note name)."""
    if node.label.strip():
        return node.label_size + 12.0
    return _DECORATED_TOP.get(node.sticky_note.style, PAD)


def line_height(node):
    return node.sticky_note.font_size * LINE_SPACING


def text_color(color):
    r, g, b = color[:3]
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return (0.12, 0.11, 0.10, 1.0) if luminance > 0.45 else (0.96, 0.95, 0.92, 1.0)


def note_color(node):
    if node.use_custom_color:
        return tuple(node.color)
    return tuple(bpy.context.preferences.themes[0].node_editor.frame_node)[:3]


# -- text layout -----------------------------------------------------------


def measure_fn(font_size):
    """Width of a string in note units at ``font_size``."""
    factor = font_size / REF_SIZE

    def measure(s):
        if not s:
            return 0.0
        blf.size(FONT, REF_SIZE)
        return blf.dimensions(FONT, s)[0] * factor

    return measure


_layout_cache = {}


def layout(node, text=None):
    """Wrapped lines (in note units) for a note. Returns (text, lines, measure)."""
    if text is None:
        text = note_body(node)
    size = node.sticky_note.font_size
    width = max(1.0, node.width - 2 * PAD)
    measure = measure_fn(size)
    key = (text, round(width, 2), size)
    lines = _layout_cache.get(key)
    if lines is None:
        if len(_layout_cache) > 512:
            _layout_cache.clear()
        lines = _layout_cache[key] = wrap(text, width, measure)
    return text, lines, measure


def fitted_height(node, text=None):
    _text, lines, _m = layout(node, text)
    return max(header_height(node) + len(lines) * line_height(node) + PAD * 1.5, 40.0)


def fit_height(node, text=None):
    if node.sticky_note.auto_height:
        h = fitted_height(node, text)
        if abs(node.height - h) > 0.5:
            node.height = h


_fit_pending = False


def _fit_all():
    global _fit_pending
    _fit_pending = False
    from .props import iter_notes

    for _tree, node in iter_notes():
        if node.id_data.library is None and (editing is None or not editing.matches(node.id_data, node)):
            fit_height(node)
    return None


def _schedule_fit():
    # Data must not be written from a draw callback, so defer to a timer.
    global _fit_pending
    if not _fit_pending:
        _fit_pending = True
        bpy.app.timers.register(_fit_all, first_interval=0.0)


# -- gpu helpers -----------------------------------------------------------


def _fill(layers):
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    for tris, rgba in layers:
        if not tris:
            continue
        batch = batch_for_shader(shader, 'TRIS', {"pos": tris})
        shader.uniform_float("color", rgba)
        batch.draw(shader)


def _visible_notes(context):
    space = context.space_data
    tree = getattr(space, "edit_tree", None)
    if tree is None:
        return None, []
    return tree, [n for n in tree.nodes if is_note(n)]


# -- draw callbacks --------------------------------------------------------


class _PixelSpace:
    """Maps note rectangles to region pixels for the current view."""

    def __init__(self, region):
        v2d = region.view2d
        self.region = region
        self.ox, self.oy = v2d.view_to_region(0.0, 0.0, clip=False)
        zx, _ = v2d.view_to_region(10000.0, 0.0, clip=False)
        self.zoom = (zx - self.ox) / 10000.0
        self.scale = ui_scale()
        self.k = self.scale * self.zoom  # pixels per note unit

    def rect(self, node):
        vx0, vy0, vx1, vy1 = note_rect_view(node, self.scale)
        z = self.zoom
        return self.ox + vx0 * z, self.oy + vy0 * z, self.ox + vx1 * z, self.oy + vy1 * z

    def visible(self, r):
        m = 80 * self.k
        return not (r[2] < -m or r[0] > self.region.width + m or r[3] < -m or r[1] > self.region.height + m)


def draw_under():
    """BACKDROP pass (after the grid, before nodes), in region pixels:
    the solid body plus anything that sticks out of the frame."""
    context = bpy.context
    _tree, notes = _visible_notes(context)
    if not notes:
        return
    _measure_scale(notes)
    px = _PixelSpace(context.region)
    gpu.state.blend_set('ALPHA')
    for node in notes:
        r = px.rect(node)
        if px.visible(r):
            _fill(shapes.under(node.sticky_note.style, r, px.k, note_color(node)))
    gpu.state.blend_set('NONE')


def draw_over():
    """POST_PIXEL pass, in region pixels: decorations on top, body text, caret."""
    context = bpy.context
    tree, notes = _visible_notes(context)
    if not notes:
        return
    px = _PixelSpace(context.region)
    k = px.k
    background = tuple(context.preferences.themes[0].node_editor.space.back)[:3]

    gpu.state.blend_set('ALPHA')
    needs_fit = False
    for node in notes:
        r = px.rect(node)
        if not px.visible(r):
            continue
        color = note_color(node)
        _fill(shapes.over(node.sticky_note.style, r, k, color, background))

        state = editing if editing is not None and editing.matches(tree, node) else None
        text = state.buffer.text if state else None
        text, lines, _m = layout(node, text)
        if state is None and node.sticky_note.auto_height and abs(node.height - fitted_height(node, text)) > 0.5:
            needs_fit = True
        _draw_text(node, r, k, text, lines, color, state)
        if state is not None:
            _draw_edit_outline(r, k)
    gpu.state.blend_set('NONE')
    if needs_fit:
        _schedule_fit()


def _draw_edit_outline(r, k):
    x0, y0, x1, y1 = r
    t = max(1.5, 1.5 * k)
    o = 3 * k
    accent = (0.33, 0.62, 1.0, 0.95)
    _fill([
        (shapes.rect(x0 - o, y1 + o - t, x1 + o, y1 + o), accent),
        (shapes.rect(x0 - o, y0 - o, x1 + o, y0 - o + t), accent),
        (shapes.rect(x0 - o, y0 - o, x0 - o + t, y1 + o), accent),
        (shapes.rect(x1 + o - t, y0 - o, x1 + o, y1 + o), accent),
    ])


def _draw_text(node, r, k, text, lines, color, state):
    x0, y0, x1, y1 = r
    size_px = node.sticky_note.font_size * k
    if size_px < MIN_TEXT_PX:
        return
    line_px = line_height(node) * k
    left = x0 + PAD * k
    top = y1 - header_height(node) * k
    fg = text_color(color)

    blf.size(FONT, size_px)

    def baseline(i):
        return top - i * line_px - size_px * 0.95

    def px_width(s):
        return blf.dimensions(FONT, s)[0] if s else 0.0

    if state is not None and state.buffer.has_selection():
        a, b = state.buffer.selection()
        sel = []
        for i, line in enumerate(lines):
            lo, hi = max(a, line.start), min(b, line.end)
            ends_in_newline = not line.soft and b > line.end and a <= line.end
            if lo > hi or (lo == hi and not ends_in_newline):
                continue
            sx = left + px_width(text[line.start:lo])
            ex = left + px_width(text[line.start:hi]) + (size_px * 0.3 if ends_in_newline else 0.0)
            by = baseline(i)
            sel.append((shapes.rect(sx, by - size_px * 0.3, ex, by + size_px * 1.0), (0.30, 0.55, 1.0, 0.38)))
        _fill(sel)

    blf.color(FONT, *fg)
    blf.enable(FONT, blf.CLIPPING)
    blf.clipping(FONT, x0, y0, x1, y1)
    for i, line in enumerate(lines):
        by = baseline(i)
        if by > y1:
            continue
        if by < y0 - line_px:
            break
        segment = text[line.start:line.end]
        if segment.strip():
            blf.position(FONT, left, by, 0)
            blf.draw(FONT, segment)
    blf.disable(FONT, blf.CLIPPING)

    if state is not None and state.caret_visible:
        caret = state.buffer.caret
        i = line_index(lines, caret)
        line = lines[i]
        cx = left + px_width(text[line.start:caret])
        by = baseline(i)
        w = max(1.0, 0.11 * size_px)
        _fill([(shapes.rect(cx, by - size_px * 0.25, cx + w, by + size_px * 0.95), fg)])


# -- registration ----------------------------------------------------------

_handles = []


def tag_redraw_all():
    wm = bpy.context.window_manager
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type == 'NODE_EDITOR':
                area.tag_redraw()


def register():
    space = bpy.types.SpaceNodeEditor
    _handles.append(space.draw_handler_add(draw_under, (), 'WINDOW', 'BACKDROP'))
    _handles.append(space.draw_handler_add(draw_over, (), 'WINDOW', 'POST_PIXEL'))


def unregister():
    global editing
    editing = None
    for handle in _handles:
        bpy.types.SpaceNodeEditor.draw_handler_remove(handle, 'WINDOW')
    _handles.clear()
    _layout_cache.clear()
