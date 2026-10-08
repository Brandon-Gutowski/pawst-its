# SPDX-FileCopyrightText: 2026 Brandon Gutowski
#
# SPDX-License-Identifier: GPL-3.0-or-later

import bpy
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty

from .props import COLOR_PRESETS, STYLES


class PawstItsPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    default_color: FloatVectorProperty(
        name="Default Color",
        subtype='COLOR_GAMMA',
        size=3,
        min=0.0,
        max=1.0,
        default=COLOR_PRESETS[0][2],
    )
    default_style: EnumProperty(name="Default Style", items=STYLES, default="CAT")
    default_font_size: FloatProperty(name="Default Font Size", default=14.0, min=6.0, max=96.0)
    default_width: FloatProperty(name="Default Width", default=260.0, min=60.0, max=2000.0)
    default_height: FloatProperty(name="Default Height", default=140.0, min=40.0, max=2000.0)

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        col = layout.column()
        col.prop(self, "default_style")
        col.prop(self, "default_color")
        col.prop(self, "default_font_size")
        col.prop(self, "default_width")
        col.prop(self, "default_height")
        layout.label(
            text="Shift+P drops a note, double-click edits one. Rebind under Keymap > Node Editor.",
            icon='INFO',
        )


class _Defaults:
    default_color = COLOR_PRESETS[0][2]
    default_style = "CAT"
    default_font_size = 14.0
    default_width = 260.0
    default_height = 140.0


def get_prefs():
    addon = bpy.context.preferences.addons.get(__package__)
    return addon.preferences if addon is not None else _Defaults


def register():
    bpy.utils.register_class(PawstItsPreferences)


def unregister():
    bpy.utils.unregister_class(PawstItsPreferences)
