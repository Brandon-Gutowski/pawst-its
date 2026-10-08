import math

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty

from . import draw
from .prefs import get_prefs
from .props import COLOR_PRESETS, STYLES, TEXT_NAME, color_icon, ensure_own_text, is_note, note_body, set_body
from .text_layout import TextBuffer, hit_test, next_word, prev_word

# Events the editor lets through so the view can be panned/zoomed while typing.
NAVIGATION_EVENTS = {
    'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'WHEELINMOUSE', 'WHEELOUTMOUSE',
    'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'MOUSESMARTZOOM', 'NDOF_MOTION',
}
MODIFIER_KEYS = {
    'LEFT_CTRL', 'RIGHT_CTRL', 'LEFT_SHIFT', 'RIGHT_SHIFT', 'LEFT_ALT', 'RIGHT_ALT', 'OSKEY',
    'APP', 'HYPER',
}
STATUS_HINT = "Typing note  ·  Esc / Ctrl+Enter / click outside: done  ·  Ctrl+A/C/X/V"


def _node_editor_poll(context):
    space = context.space_data
    return (
        space is not None
        and space.type == 'NODE_EDITOR'
        and space.edit_tree is not None
        and space.edit_tree.library is None
    )


def selected_notes(context):
    tree = context.space_data.edit_tree
    notes = [n for n in tree.nodes if n.select and is_note(n)]
    active = tree.nodes.active
    if not notes and is_note(active):
        notes = [active]
    return notes


def create_note(tree, location, body=""):
    prefs = get_prefs()
    for node in tree.nodes:
        node.select = False
    frame = tree.nodes.new("NodeFrame")
    frame.name = "PawstIt"
    frame.label = ""
    frame.shrink = False
    frame.label_size = 16
    frame.width = prefs.default_width
    frame.height = prefs.default_height
    frame.use_custom_color = True
    frame.color = prefs.default_color
    frame.location = location
    props = frame.pawst_it
    props.is_note = True
    props.style = prefs.default_style
    props.font_size = prefs.default_font_size
    props.text = bpy.data.texts.new(TEXT_NAME)
    if body:
        props.text.from_string(body)
    draw.fit_height(frame)
    frame.select = True
    tree.nodes.active = frame
    return frame


def _window_region(area):
    return next(r for r in area.regions if r.type == 'WINDOW')


def note_at(context, mx, my):
    """Topmost note under region coordinates (mx, my)."""
    tree = context.space_data.edit_tree
    vx, vy = context.region.view2d.region_to_view(mx, my)
    scale = draw.ui_scale()
    for node in reversed(list(tree.nodes)):
        if is_note(node):
            x0, y0, x1, y1 = draw.note_rect_view(node, scale)
            if x0 <= vx <= x1 and y0 <= vy <= y1:
                return node
    return None


class NODE_OT_pawst_it_add(bpy.types.Operator):
    """Drop a Pawst-It at the mouse cursor and start typing"""

    bl_idname = "node.pawst_it_add"
    bl_label = "Pawst-It"
    bl_options = {'UNDO'}

    edit: BoolProperty(name="Start Typing", default=True, options={'SKIP_SAVE'})
    text: StringProperty(name="Text", default="", options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return _node_editor_poll(context)

    def invoke(self, context, event):
        space = context.space_data
        region = context.region
        if region is not None and region.type == 'WINDOW':
            space.cursor_location_from_region(event.mouse_region_x, event.mouse_region_y)
            self._location = tuple(space.cursor_location)
        else:
            # From the sidebar or a menu outside the canvas: center of the view.
            window = _window_region(context.area)
            vx, vy = window.view2d.region_to_view(window.width / 2, window.height / 2)
            scale = draw.ui_scale()
            prefs = get_prefs()
            self._location = (vx / scale - prefs.default_width / 2, vy / scale + prefs.default_height / 2)
        return self.execute(context)

    def execute(self, context):
        space = context.space_data
        location = getattr(self, "_location", None) or tuple(space.cursor_location)
        node = create_note(space.edit_tree, location, self.text)
        if self.edit:
            with context.temp_override(region=_window_region(context.area)):
                bpy.ops.node.pawst_it_edit('INVOKE_DEFAULT', node_name=node.name, is_new=True)
        return {'FINISHED'}


class NODE_OT_pawst_it_edit(bpy.types.Operator):
    """Type into a Pawst-It"""

    bl_idname = "node.pawst_it_edit"
    bl_label = "Edit Pawst-It"
    bl_options = {'UNDO'}

    node_name: StringProperty(options={'SKIP_SAVE', 'HIDDEN'})
    is_new: BoolProperty(options={'SKIP_SAVE', 'HIDDEN'})
    hovered: BoolProperty(
        name="Under Mouse",
        description="Edit the note under the mouse; pass the event through if there is none",
        options={'SKIP_SAVE'},
    )

    @classmethod
    def poll(cls, context):
        return _node_editor_poll(context)

    # -- helpers ---------------------------------------------------------

    def _node(self, context):
        tree = context.space_data.edit_tree
        if tree is None or tree.as_pointer() != self._tree_ptr:
            return None
        node = tree.nodes.get(self._name)
        return node if is_note(node) else None

    def _layout(self, node):
        return draw.layout(node, self._buffer.text)

    def _index_at(self, context, node, mx, my):
        vx, vy = context.region.view2d.region_to_view(mx, my)
        scale = draw.ui_scale()
        x0, _y0, _x1, y1 = draw.note_rect_view(node, scale)
        lx = (vx - x0) / scale - draw.PAD
        ly = (y1 - vy) / scale - draw.header_height(node)
        text, lines, measure = self._layout(node)
        i = min(max(int(math.floor(ly / draw.line_height(node))), 0), len(lines) - 1)
        return hit_test(text, lines[i], lx, measure)

    def _sync(self, context, node):
        set_body(node, self._buffer.text)
        draw.fit_height(node, self._buffer.text)
        self._state.caret_visible = True
        context.area.tag_redraw()

    def _finish(self, context):
        wm = context.window_manager
        if self._timer is not None:
            wm.event_timer_remove(self._timer)
            self._timer = None
        context.workspace.status_text_set(None)
        draw.editing = None
        node = self._node(context)
        if node is not None and self.is_new and not self._buffer.text.strip() and not node.label:
            text = node.pawst_it.text
            context.space_data.edit_tree.nodes.remove(node)
            if text is not None and text.users == 0:
                bpy.data.texts.remove(text)
        context.area.tag_redraw()

    # -- operator --------------------------------------------------------

    def invoke(self, context, event):
        if context.region is None or context.region.type != 'WINDOW':
            # From the sidebar: run the editor in the canvas region instead.
            node = context.space_data.edit_tree.nodes.active
            if not is_note(node):
                return {'CANCELLED'}
            with context.temp_override(region=_window_region(context.area)):
                return bpy.ops.node.pawst_it_edit('INVOKE_DEFAULT', node_name=node.name)
        tree = context.space_data.edit_tree
        if self.node_name:
            node = tree.nodes.get(self.node_name)
        elif self.hovered:
            node = note_at(context, event.mouse_region_x, event.mouse_region_y)
        else:
            node = tree.nodes.active
        if not is_note(node):
            if self.hovered:
                return {'PASS_THROUGH'}
            self.report({'WARNING'}, "No Pawst-It selected")
            return {'CANCELLED'}
        if draw.editing is not None:
            return {'CANCELLED'}

        ensure_own_text(node)
        for other in tree.nodes:
            other.select = False
        node.select = True
        tree.nodes.active = node

        self._tree_ptr = tree.as_pointer()
        self._name = node.name
        self._buffer = TextBuffer(note_body(node))
        self._dragging = False
        if self.hovered:
            self._buffer.click(self._index_at(context, node, event.mouse_region_x, event.mouse_region_y))
        self._state = draw.EditState(tree, node.name, self._buffer)
        draw.editing = self._state

        wm = context.window_manager
        self._timer = wm.event_timer_add(0.5, window=context.window)
        context.workspace.status_text_set(STATUS_HINT)
        wm.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        node = self._node(context)
        if node is None or draw.editing is not self._state:
            self._finish(context)
            return {'CANCELLED'}
        try:
            return self._handle(context, event, node)
        except Exception:
            self._finish(context)
            raise

    def _handle(self, context, event, node):
        etype, value = event.type, event.value
        buf = self._buffer
        ctrl = event.ctrl or event.oskey
        shift = event.shift

        if etype == 'TIMER':
            self._state.caret_visible = not self._state.caret_visible
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if etype in NAVIGATION_EVENTS:
            return {'PASS_THROUGH'}
        if etype in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            if self._dragging:
                buf.click(self._index_at(context, node, event.mouse_region_x, event.mouse_region_y), extend=True)
                self._state.caret_visible = True
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            return {'PASS_THROUGH'}

        if etype == 'LEFTMOUSE':
            inside = note_at(context, event.mouse_region_x, event.mouse_region_y) == node
            if value == 'RELEASE':
                self._dragging = False
                return {'RUNNING_MODAL'}
            if not inside:
                self._finish(context)
                return {'FINISHED', 'PASS_THROUGH'}
            idx = self._index_at(context, node, event.mouse_region_x, event.mouse_region_y)
            if value == 'DOUBLE_CLICK':
                buf.click(prev_word(buf.text, idx) if idx and not buf.text[idx - 1].isspace() else idx)
                buf.click(next_word(buf.text, idx), extend=True)
            elif value == 'PRESS':
                buf.click(idx, extend=shift)
                self._dragging = True
            self._state.caret_visible = True
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        if etype == 'RIGHTMOUSE' and value == 'PRESS':
            self._finish(context)
            return {'FINISHED', 'PASS_THROUGH'}

        if value != 'PRESS' or etype in MODIFIER_KEYS:
            return {'RUNNING_MODAL'}

        if etype == 'ESC' or (etype in {'RET', 'NUMPAD_ENTER'} and ctrl):
            self._finish(context)
            return {'FINISHED'}

        text_before = buf.text
        _text, lines, measure = self._layout(node)
        word = event.alt or event.ctrl  # Alt on macOS, Ctrl elsewhere
        if etype in {'RET', 'NUMPAD_ENTER'}:
            buf.insert("\n")
        elif etype == 'TAB':
            buf.insert("    ")
        elif etype == 'BACK_SPACE':
            buf.backspace(word=word)
        elif etype == 'DEL':
            buf.delete_forward(word=word)
        elif etype == 'LEFT_ARROW':
            buf.home(lines, shift) if event.oskey else buf.left(shift, word)
        elif etype == 'RIGHT_ARROW':
            buf.end(lines, shift) if event.oskey else buf.right(shift, word)
        elif etype == 'UP_ARROW':
            buf.vertical(lines, measure, -1, shift)
        elif etype == 'DOWN_ARROW':
            buf.vertical(lines, measure, 1, shift)
        elif etype == 'HOME':
            buf.home(lines, shift)
        elif etype == 'END':
            buf.end(lines, shift)
        elif ctrl and etype == 'A':
            buf.select_all()
        elif ctrl and etype == 'C':
            if buf.has_selection():
                context.window_manager.clipboard = buf.selected_text()
        elif ctrl and etype == 'X':
            if buf.has_selection():
                context.window_manager.clipboard = buf.cut()
        elif ctrl and etype == 'V':
            buf.insert(context.window_manager.clipboard.replace("\r\n", "\n").replace("\r", "\n"))
        elif ctrl:
            # Any other shortcut (save, undo, ...) ends editing and runs normally.
            self._finish(context)
            return {'FINISHED', 'PASS_THROUGH'}
        elif event.unicode and event.unicode.isprintable():
            buf.insert(event.unicode)

        if buf.text != text_before:
            self._sync(context, node)
        else:
            self._state.caret_visible = True
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        self._finish(context)


class NODE_OT_pawst_it_set_color(bpy.types.Operator):
    """Set the color of the selected Pawst-Its"""

    bl_idname = "node.pawst_it_set_color"
    bl_label = "Pawst-It Color"
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(name="Color", items=[(p[0], p[1], "", color_icon(p[3]), i) for i, p in enumerate(COLOR_PRESETS)])

    @classmethod
    def poll(cls, context):
        return _node_editor_poll(context) and bool(selected_notes(context))

    def execute(self, context):
        color = next(p[2] for p in COLOR_PRESETS if p[0] == self.preset)
        for node in selected_notes(context):
            node.use_custom_color = True
            node.color = color
        return {'FINISHED'}


class NODE_OT_pawst_it_set_style(bpy.types.Operator):
    """Set the frame style of the selected Pawst-Its"""

    bl_idname = "node.pawst_it_set_style"
    bl_label = "Pawst-It Style"
    bl_options = {'REGISTER', 'UNDO'}

    style: EnumProperty(name="Style", items=STYLES)

    @classmethod
    def poll(cls, context):
        return _node_editor_poll(context) and bool(selected_notes(context))

    def execute(self, context):
        for node in selected_notes(context):
            node.pawst_it.style = self.style
        return {'FINISHED'}


classes = (
    NODE_OT_pawst_it_add,
    NODE_OT_pawst_it_edit,
    NODE_OT_pawst_it_set_color,
    NODE_OT_pawst_it_set_style,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
