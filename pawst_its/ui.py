import bpy

from .props import COLOR_PRESETS, is_note, note_body

# Add > Layout menu ids across Blender versions and editors.
LAYOUT_MENUS = (
    "NODE_MT_category_layout",
    "NODE_MT_category_LAYOUT",
    "NODE_MT_category_GEO_LAYOUT",
    "NODE_MT_category_shader_layout",
    "NODE_MT_category_compositor_layout",
    "NODE_MT_category_texture_layout",
)
PREVIEW_LINES = 6


def active_note(context):
    space = context.space_data
    tree = getattr(space, "edit_tree", None)
    node = tree.nodes.active if tree is not None else None
    return node if is_note(node) else None


def draw_color_presets(layout):
    row = layout.row(align=True)
    for ident, label, _color, icon in COLOR_PRESETS:
        op = row.operator("node.pawst_it_set_color", text="", icon=icon)
        op.preset = ident


class NODE_PT_pawst_it(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Pawst-Its"
    bl_label = "Pawst-It"

    @classmethod
    def poll(cls, context):
        return getattr(context.space_data, "edit_tree", None) is not None

    def draw(self, context):
        layout = self.layout
        node = active_note(context)
        if node is None:
            layout.operator("node.pawst_it_add", text="Add Pawst-It", icon='ADD')
            layout.label(text="Shift+P over the canvas", icon='INFO')
            return

        props = node.pawst_it
        layout.operator("node.pawst_it_edit", text="Edit Text", icon='GREASEPENCIL')

        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(node, "label", text="Name")
        col.prop(props, "style")
        col.prop(node, "color")
        draw_color_presets(layout)

        col = layout.column()
        col.use_property_split = True
        col.use_property_decorate = False
        col.prop(props, "font_size")
        col.prop(node, "label_size", text="Name Size")
        col.prop(node, "width")
        col.prop(props, "auto_height")
        sub = col.column()
        sub.active = not props.auto_height
        sub.prop(node, "height")

        body = note_body(node)
        if body.strip():
            box = layout.box()
            col = box.column(align=True)
            col.scale_y = 0.8
            lines = body.splitlines()
            for line in lines[:PREVIEW_LINES]:
                col.label(text=line)
            if len(lines) > PREVIEW_LINES:
                col.label(text="…")


class NODE_MT_pawst_it_style(bpy.types.Menu):
    bl_label = "Style"

    def draw(self, _context):
        self.layout.operator_enum("node.pawst_it_set_style", "style")


class NODE_MT_pawst_it_color(bpy.types.Menu):
    bl_label = "Color"

    def draw(self, _context):
        self.layout.operator_enum("node.pawst_it_set_color", "preset")


def draw_context_menu(self, context):
    if active_note(context) is None:
        return
    layout = self.layout
    layout.separator()
    layout.operator("node.pawst_it_edit", text="Edit Pawst-It", icon='GREASEPENCIL')
    layout.menu("NODE_MT_pawst_it_style")
    layout.menu("NODE_MT_pawst_it_color")


def draw_add_menu(self, _context):
    self.layout.operator("node.pawst_it_add", text="Pawst-It", icon='FILE_TEXT')


classes = (NODE_PT_pawst_it, NODE_MT_pawst_it_style, NODE_MT_pawst_it_color)


def _layout_menus():
    return [m for m in (getattr(bpy.types, name, None) for name in LAYOUT_MENUS) if m is not None]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.NODE_MT_context_menu.append(draw_context_menu)
    for menu in _layout_menus():
        menu.append(draw_add_menu)


def unregister():
    for menu in _layout_menus():
        menu.remove(draw_add_menu)
    bpy.types.NODE_MT_context_menu.remove(draw_context_menu)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
