# SPDX-FileCopyrightText: 2026 Brandon Gutowski
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Headless end-to-end check. Run via tests/run_smoke.sh (isolates Blender's user config).

blender -b --factory-startup --python tests/smoke_blender.py -- <extension.zip> <scratch_dir>
"""

import os
import sys
import traceback

import bpy

zip_path, scratch = sys.argv[sys.argv.index("--") + 1:][:2]
PKG = "bl_ext.user_default.pawst_its"
failures = []


def check(cond, msg):
    print(("ok   " if cond else "FAIL ") + msg)
    if not cond:
        failures.append(msg)


def addon():
    return sys.modules[PKG]


def trees():
    scene = bpy.context.scene
    mat = bpy.data.materials.new("SmokeMat")
    mat.use_fake_user = True
    if hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    gn = bpy.data.node_groups.new("SmokeGN", "GeometryNodeTree")
    gn.use_fake_user = True
    if hasattr(scene, "compositing_node_group"):  # 5.0+
        comp = bpy.data.node_groups.new("SmokeComp", "CompositorNodeTree")
        scene.compositing_node_group = comp
    else:
        scene.use_nodes = True
        comp = scene.node_tree
    return {"shader": mat.node_tree, "geometry": gn, "compositor": comp}


def main():
    bpy.ops.extensions.package_install_files(filepath=zip_path, repo="user_default", enable_on_install=True)
    check(PKG in bpy.context.preferences.addons, "extension installed and enabled")
    ops = sys.modules[PKG + ".ops"]
    props = sys.modules[PKG + ".props"]
    draw = sys.modules[PKG + ".draw"]

    # Every icon the UI uses must exist in this Blender (icons get renamed between versions).
    valid_icons = set(bpy.types.UILayout.bl_rna.functions["operator"].parameters["icon"].enum_items.keys())
    used = {props.color_icon(p[3]) for p in props.COLOR_PRESETS} | {"ADD", "INFO", "GREASEPENCIL", "FILE_TEXT"}
    check(used <= valid_icons and "NONE" not in used, f"all UI icons exist ({sorted(used - valid_icons) or 'ok'})")
    color_items = bpy.ops.node.pawst_it_set_color.get_rna_type().properties["preset"].enum_items
    check(all(item.icon in valid_icons for item in color_items), "color menu icons exist")

    names = {}
    for kind, tree in trees().items():
        node = ops.create_note(tree, (100.0, 200.0), "hello\nworld " * 20)
        names[kind] = (tree.name, node.name)
        check(node.bl_idname == "NodeFrame" and props.is_note(node), f"{kind}: note is a Pawst-It Frame")
        check(props.note_body(node).startswith("hello\nworld"), f"{kind}: body stored in Text")
        check(node.pawst_it.text.name.startswith(".PawstIt"), f"{kind}: hidden Text name")
        check(node.text is None, f"{kind}: frame.text detached during session")
        check(not node.shrink and node.use_custom_color, f"{kind}: frame configured")
        check(tuple(node.location) == (100.0, 200.0), f"{kind}: placed at location")
        check(node.height > 140.0, f"{kind}: auto height grew to fit text ({node.height:.0f})")
        node.label = f"{kind} note"
        node.pawst_it.style = {"shader": "PEEK", "geometry": "PAW", "compositor": "LOAF"}[kind]

    # Copy-on-write when two notes share a Text (as after Shift+D).
    gn = bpy.data.node_groups["SmokeGN"]
    a = gn.nodes[names["geometry"][1]]
    b = ops.create_note(gn, (500.0, 0.0))
    shared = a.pawst_it.text
    b.pawst_it.text = shared
    own = props.ensure_own_text(b)
    check(own != shared and own.as_string() == shared.as_string(), "duplicate note gets its own Text copy")
    props.set_body(b, "changed")
    check(props.note_body(a).startswith("hello"), "editing the duplicate leaves the original alone")

    # Text layout sanity.
    text, lines, _m = draw.layout(a)
    check(len(lines) > 3, f"long text wraps ({len(lines)} lines)")

    # A note as saved by v1 ("Sticky Notes"): raw ID-property group + frame.text.
    legacy_text = bpy.data.texts.new(".StickyNote")
    legacy_text.from_string("legacy note")
    old = gn.nodes.new("NodeFrame")
    old.name = "OldNote"
    old.text = legacy_text
    old["sticky_note"] = {"is_note": True, "text": legacy_text, "font_size": 18.0, "auto_height": True, "style": 5}

    path = os.path.join(scratch, "smoke.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    check(all(n.text is None for _t, n in props.iter_notes()), "frame.text detached again after save")

    # Without the add-on: the native Frame shows the text.
    bpy.ops.preferences.addon_disable(module=PKG)
    bpy.ops.wm.open_mainfile(filepath=path)
    frames = [n for t in props.iter_node_trees() for n in t.nodes if n.bl_idname == "NodeFrame"]
    check(len(frames) == 5, f"5 frames in saved file ({len(frames)})")
    check(all(f.text is not None and f.text.as_string() for f in frames), "fallback: every frame has its Text")
    labels = sorted(f.label for f in frames)
    check("shader note" in labels and "compositor note" in labels, "names saved as frame labels")

    # Re-enable: load_post detaches again and the data is intact.
    bpy.ops.preferences.addon_enable(module=PKG)
    bpy.ops.wm.open_mainfile(filepath=path)
    props = sys.modules[PKG + ".props"]
    notes = list(props.iter_notes())
    check(len(notes) == 5, f"5 notes after reload, incl. migrated v1 note ({len(notes)})")
    check(all(n.text is None for _t, n in notes), "frames detached on load with add-on")
    styles = {n.pawst_it.style for _t, n in notes}
    check({"PEEK", "PAW", "LOAF", "CAT"} <= styles, f"styles persisted ({sorted(styles)})")

    old = bpy.data.node_groups["SmokeGN"].nodes["OldNote"]
    check(props.is_note(old) and props.note_body(old) == "legacy note", "v1 note migrated with its text")
    check(old.pawst_it.font_size == 18.0 and old.pawst_it.style == "CAT", "v1 font size kept, retired style -> Cat Head")
    check("sticky_note" not in old.keys(), "v1 property group removed")

    bpy.ops.preferences.addon_disable(module=PKG)
    check(all(n.text is not None for _t, n in notes), "disabling the add-on reattaches fallback text")

    # Updating / re-enabling in the same session must detach again (no doubled text).
    bpy.ops.preferences.addon_enable(module=PKG)
    sys.modules[PKG]._adopt_open_file()  # the timer registered by register(); run it now (no event loop headless)
    check(all(n.text is None for _t, n in notes), "re-enabling the add-on detaches the text again")
    bpy.ops.preferences.addon_disable(module=PKG)


try:
    main()
except Exception:
    traceback.print_exc()
    failures.append("exception")

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'ALL SMOKE CHECKS PASSED'}")
sys.stdout.flush()
os._exit(1 if failures else 0)
