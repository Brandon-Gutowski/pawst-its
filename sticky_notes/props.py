"""Sticky note data: the property group stored on Frame nodes, plus helpers."""

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty

TEXT_NAME = ".StickyNote"  # leading dot hides it from most ID pickers

STYLES = [
    ("CLASSIC", "Classic", "Plain note with a soft shadow and a glue strip"),
    ("PUSHPIN", "Pushpin", "Pinned to the board with a round pushpin"),
    ("TAPE", "Washi Tape", "Held up by two strips of washi tape"),
    ("DOGEAR", "Dog-Ear", "Bottom-right corner folded over"),
    ("BUBBLE", "Speech Bubble", "Speech bubble with a tail"),
    ("CLOUD", "Thought Cloud", "Fluffy thought cloud"),
]

# (identifier, label, sRGB color, icon). Icons are Blender's colored tag icons.
COLOR_PRESETS = [
    ("LEMON", "Lemon", (1.00, 0.89, 0.45), "SEQUENCE_COLOR_03"),
    ("PEACH", "Peach", (1.00, 0.74, 0.55), "SEQUENCE_COLOR_02"),
    ("CORAL", "Coral", (1.00, 0.58, 0.56), "SEQUENCE_COLOR_01"),
    ("PINK", "Pink", (1.00, 0.70, 0.84), "SEQUENCE_COLOR_07"),
    ("LAVENDER", "Lavender", (0.80, 0.72, 1.00), "SEQUENCE_COLOR_06"),
    ("SKY", "Sky", (0.62, 0.82, 1.00), "SEQUENCE_COLOR_05"),
    ("MINT", "Mint", (0.66, 0.93, 0.76), "SEQUENCE_COLOR_04"),
    ("LATTE", "Latte", (0.85, 0.74, 0.62), "SEQUENCE_COLOR_08"),
    ("PAPER", "Paper", (0.95, 0.94, 0.90), "SEQUENCE_COLOR_09"),
]


def _redraw(_self, context):
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == 'NODE_EDITOR':
                area.tag_redraw()


def _refit(self, context):
    # Imported lazily: draw.py depends on blf/gpu, props.py should not.
    from . import draw

    node = owner_node(self)
    if node is not None:
        draw.fit_height(node)
    _redraw(self, context)


class StickyNoteProps(bpy.types.PropertyGroup):
    is_note: BoolProperty(name="Is Sticky Note", default=False)
    text: PointerProperty(name="Text", type=bpy.types.Text)
    style: EnumProperty(name="Style", items=STYLES, default="CLASSIC", update=_redraw)
    font_size: FloatProperty(
        name="Font Size", default=14.0, min=6.0, max=96.0, soft_max=48.0, update=_refit
    )
    auto_height: BoolProperty(
        name="Auto Height",
        description="Grow and shrink the note to fit its text",
        default=True,
        update=_refit,
    )


def owner_node(props):
    """The Frame node a StickyNoteProps instance belongs to."""
    ptr = props.as_pointer()
    for node in getattr(props.id_data, "nodes", ()):
        if node.bl_idname == "NodeFrame" and node.sticky_note.as_pointer() == ptr:
            return node
    return None


def is_note(node):
    return node is not None and node.bl_idname == "NodeFrame" and node.sticky_note.is_note


def iter_node_trees():
    yield from bpy.data.node_groups
    for collection in (
        bpy.data.materials,
        bpy.data.worlds,
        bpy.data.lights,
        bpy.data.textures,
        bpy.data.linestyles,
        bpy.data.scenes,
    ):
        for idblock in collection:
            tree = getattr(idblock, "node_tree", None)  # scene.node_tree is pre-5.0 compositor
            if tree is not None:
                yield tree


def iter_notes():
    for tree in iter_node_trees():
        for node in tree.nodes:
            if is_note(node):
                yield tree, node


def note_body(node):
    text = node.sticky_note.text
    return text.as_string() if text is not None else ""


def ensure_own_text(node):
    """Return a Text used by this note only; copy-on-write after node duplication."""
    props = node.sticky_note
    text = props.text
    if text is None:
        text = bpy.data.texts.new(TEXT_NAME)
    elif text.library is not None or any(
        other.sticky_note.text == text for _tree, other in iter_notes() if other != node
    ):
        text = text.copy()
    if props.text != text:
        props.text = text
    return text


def set_body(node, body):
    text = node.sticky_note.text or ensure_own_text(node)
    if text.as_string() != body:
        text.from_string(body)


def attach_fallback_text(attach):
    """Point each note frame at its Text so Blender draws it natively (no add-on),
    or detach it so only the add-on draws it."""
    for _tree, node in iter_notes():
        if node.id_data.library is not None:
            continue
        want = node.sticky_note.text if attach else None
        if node.text != want:
            try:
                node.text = want
            except (AttributeError, RuntimeError):
                pass


def register():
    bpy.utils.register_class(StickyNoteProps)
    bpy.types.NodeFrame.sticky_note = PointerProperty(type=StickyNoteProps)


def unregister():
    del bpy.types.NodeFrame.sticky_note
    bpy.utils.unregister_class(StickyNoteProps)
