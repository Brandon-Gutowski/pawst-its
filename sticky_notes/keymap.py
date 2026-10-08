import bpy

_keymaps = []


def _warn_conflicts(kc_user):
    km = kc_user.keymaps.get("Node Editor") if kc_user else None
    if km is None:
        return
    for kmi in km.keymap_items:
        if (
            kmi.active
            and kmi.type == 'P'
            and kmi.value == 'PRESS'
            and kmi.shift == 1
            and not (kmi.ctrl or kmi.alt or kmi.oskey)
            and kmi.idname != "node.sticky_note_add"
        ):
            print(f"Sticky Notes: Shift+P also runs '{kmi.idname}' in the Node Editor; the add-on takes priority.")


def register():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon
    if kc is None:  # background mode
        return
    km = kc.keymaps.new(name="Node Editor", space_type='NODE_EDITOR')
    kmi = km.keymap_items.new("node.sticky_note_add", 'P', 'PRESS', shift=True)
    _keymaps.append((km, kmi))
    kmi = km.keymap_items.new("node.sticky_note_edit", 'LEFTMOUSE', 'DOUBLE_CLICK')
    kmi.properties.hovered = True
    _keymaps.append((km, kmi))
    _warn_conflicts(wm.keyconfigs.user)


def unregister():
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
