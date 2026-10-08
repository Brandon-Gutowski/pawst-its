# SPDX-FileCopyrightText: 2026 Brandon Gutowski
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pawst-It data: the property group stored on Frame nodes, plus helpers."""

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty

TEXT_NAME = ".PawstIt"  # leading dot hides it from most ID pickers

# Explicit numbers: enum values are stored as ints, so they must never shift.
# 0-6 were the pre-cat styles (removed); notes still holding them render as Cat Head.
STYLES = [
    ("CAT", "Cat Head", "Cat head with pointy ears and whiskers", 7),
    ("PEEK", "Peeking Cat", "A black cat peeking over the top edge", 8),
    ("PAW", "Paw Print", "Chubby paw pad with four toe beans", 9),
    ("LOAF", "Cat Loaf", "A cat loaf with a curled-up tail", 10),
    ("TAIL", "Kitty Tail", "Little ears on top and a fluffy tail", 11),
]

# (identifier, label, sRGB color, colored tag number). See color_icon().
COLOR_PRESETS = [
    ("LEMON", "Lemon", (1.00, 0.89, 0.45), "03"),
    ("PEACH", "Peach", (1.00, 0.74, 0.55), "02"),
    ("CORAL", "Coral", (1.00, 0.58, 0.56), "01"),
    ("PINK", "Pink", (1.00, 0.70, 0.84), "07"),
    ("LAVENDER", "Lavender", (0.80, 0.72, 1.00), "06"),
    ("SKY", "Sky", (0.62, 0.82, 1.00), "05"),
    ("MINT", "Mint", (0.66, 0.93, 0.76), "04"),
    ("LATTE", "Latte", (0.85, 0.74, 0.62), "08"),
    ("PAPER", "Paper", (0.95, 0.94, 0.90), "09"),
]

_icon_cache = {}


def color_icon(num):
    """Blender's colored tag icon: STRIP_COLOR_NN (4.4+) or SEQUENCE_COLOR_NN (older)."""
    if num not in _icon_cache:
        icons = bpy.types.UILayout.bl_rna.functions["operator"].parameters["icon"].enum_items.keys()
        _icon_cache[num] = next(
            (name for name in (f"STRIP_COLOR_{num}", f"SEQUENCE_COLOR_{num}") if name in icons), 'NONE'
        )
    return _icon_cache[num]


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


class PawstItProps(bpy.types.PropertyGroup):
    is_note: BoolProperty(name="Is Pawst-It", default=False)
    text: PointerProperty(name="Text", type=bpy.types.Text)
    style: EnumProperty(name="Style", items=STYLES, default="CAT", update=_redraw)
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
    """The Frame node a PawstItProps instance belongs to."""
    ptr = props.as_pointer()
    for node in getattr(props.id_data, "nodes", ()):
        if node.bl_idname == "NodeFrame" and node.pawst_it.as_pointer() == ptr:
            return node
    return None


def is_note(node):
    return node is not None and node.bl_idname == "NodeFrame" and node.pawst_it.is_note


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
    text = node.pawst_it.text
    return text.as_string() if text is not None else ""


def ensure_own_text(node):
    """Return a Text used by this note only; copy-on-write after node duplication."""
    props = node.pawst_it
    text = props.text
    if text is None:
        text = bpy.data.texts.new(TEXT_NAME)
    elif text.library is not None or any(
        other.pawst_it.text == text for _tree, other in iter_notes() if other != node
    ):
        text = text.copy()
    if props.text != text:
        props.text = text
    return text


def set_body(node, body):
    text = node.pawst_it.text or ensure_own_text(node)
    if text.as_string() != body:
        text.from_string(body)


def attach_fallback_text(attach):
    """Point each note frame at its Text so Blender draws it natively (no add-on),
    or detach it so only the add-on draws it."""
    for _tree, node in iter_notes():
        if node.id_data.library is not None:
            continue
        want = node.pawst_it.text if attach else None
        if node.text != want:
            try:
                node.text = want
            except (AttributeError, RuntimeError):
                pass


LEGACY_PROP = "sticky_note"  # v1 name of the property group, from "Sticky Notes"


def migrate_legacy():
    """Convert notes saved by v1 ("Sticky Notes") into Pawst-Its."""
    style_ids = {num: ident for ident, _name, _desc, num in STYLES}
    for tree in iter_node_trees():
        if tree.library is not None:
            continue
        for node in tree.nodes:
            if node.bl_idname != "NodeFrame":
                continue
            legacy = node.get(LEGACY_PROP)
            if legacy is None:
                continue
            if legacy.get("is_note"):
                props = node.pawst_it
                props.is_note = True
                props.text = legacy.get("text")
                props.font_size = legacy.get("font_size", props.font_size)
                props.auto_height = bool(legacy.get("auto_height", True))
                props.style = style_ids.get(legacy.get("style"), "CAT")
            del node[LEGACY_PROP]


def register():
    bpy.utils.register_class(PawstItProps)
    bpy.types.NodeFrame.pawst_it = PointerProperty(type=PawstItProps)


def unregister():
    del bpy.types.NodeFrame.pawst_it
    bpy.utils.unregister_class(PawstItProps)
