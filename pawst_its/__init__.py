# SPDX-FileCopyrightText: 2026 Brandon Gutowski
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pawst-Its: cat-themed sticky notes for every Blender node editor."""

import bpy
from bpy.app.handlers import persistent

from . import draw, keymap, ops, prefs, props, ui

_modules = (props, prefs, ops, ui, draw, keymap)


@persistent
def _save_pre(*_args):
    # Saved files carry the text on the frame itself, so they read fine without the add-on.
    props.attach_fallback_text(True)


@persistent
def _detach(*_args):
    props.attach_fallback_text(False)


@persistent
def _load_post(*_args):
    props.migrate_legacy()
    props.attach_fallback_text(False)


_handlers = (
    (bpy.app.handlers.save_pre, _save_pre),
    (bpy.app.handlers.save_post, _detach),
    (bpy.app.handlers.load_post, _load_post),
)


def register():
    for module in _modules:
        module.register()
    for handler_list, fn in _handlers:
        handler_list.append(fn)
    # Blender blocks access to bpy.data while an add-on is being enabled, so
    # adopt the open file's notes from a timer that runs right afterwards.
    bpy.app.timers.register(_adopt_open_file, first_interval=0.0)


def _adopt_open_file():
    try:
        props.migrate_legacy()
        props.attach_fallback_text(False)
    except AttributeError:
        pass  # still starting up; load_post covers it
    draw.tag_redraw_all()
    return None


def unregister():
    try:
        props.attach_fallback_text(True)
    except AttributeError:
        pass
    for handler_list, fn in _handlers:
        if fn in handler_list:
            handler_list.remove(fn)
    for module in reversed(_modules):
        module.unregister()
