"""Headless end-to-end check. Run via tests/run_smoke.sh (isolates Blender's user config).

blender -b --factory-startup --python tests/smoke_blender.py -- <extension.zip> <scratch_dir>
"""

import os
import sys
import traceback

import bpy

zip_path, scratch = sys.argv[sys.argv.index("--") + 1:][:2]
PKG = "bl_ext.user_default.sticky_notes"
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

    names = {}
    for kind, tree in trees().items():
        node = ops.create_note(tree, (100.0, 200.0), "hello\nworld " * 20)
        names[kind] = (tree.name, node.name)
        check(node.bl_idname == "NodeFrame" and props.is_note(node), f"{kind}: note is a sticky Frame")
        check(props.note_body(node).startswith("hello\nworld"), f"{kind}: body stored in Text")
        check(node.sticky_note.text.name.startswith(".StickyNote"), f"{kind}: hidden Text name")
        check(node.text is None, f"{kind}: frame.text detached during session")
        check(not node.shrink and node.use_custom_color, f"{kind}: frame configured")
        check(tuple(node.location) == (100.0, 200.0), f"{kind}: placed at location")
        check(node.height > 140.0, f"{kind}: auto height grew to fit text ({node.height:.0f})")
        node.label = f"{kind} note"
        node.sticky_note.style = "CLOUD"

    # Copy-on-write when two notes share a Text (as after Shift+D).
    gn = bpy.data.node_groups["SmokeGN"]
    a = gn.nodes[names["geometry"][1]]
    b = ops.create_note(gn, (500.0, 0.0))
    shared = a.sticky_note.text
    b.sticky_note.text = shared
    own = props.ensure_own_text(b)
    check(own != shared and own.as_string() == shared.as_string(), "duplicate note gets its own Text copy")
    props.set_body(b, "changed")
    check(props.note_body(a).startswith("hello"), "editing the duplicate leaves the original alone")

    # Text layout sanity.
    text, lines, _m = draw.layout(a)
    check(len(lines) > 3, f"long text wraps ({len(lines)} lines)")

    path = os.path.join(scratch, "smoke.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path)
    check(all(n.text is None for _t, n in props.iter_notes()), "frame.text detached again after save")

    # Without the add-on: the native Frame shows the text.
    bpy.ops.preferences.addon_disable(module=PKG)
    bpy.ops.wm.open_mainfile(filepath=path)
    frames = [n for t in props.iter_node_trees() for n in t.nodes if n.bl_idname == "NodeFrame"]
    check(len(frames) == 4, f"4 frames in saved file ({len(frames)})")
    check(all(f.text is not None and f.text.as_string() for f in frames), "fallback: every frame has its Text")
    labels = sorted(f.label for f in frames)
    check("shader note" in labels and "compositor note" in labels, "names saved as frame labels")

    # Re-enable: load_post detaches again and the data is intact.
    bpy.ops.preferences.addon_enable(module=PKG)
    bpy.ops.wm.open_mainfile(filepath=path)
    props = sys.modules[PKG + ".props"]
    notes = list(props.iter_notes())
    check(len(notes) == 4, f"4 notes after reload ({len(notes)})")
    check(all(n.text is None for _t, n in notes), "frames detached on load with add-on")
    check(any(n.sticky_note.style == "CLOUD" for _t, n in notes), "style persisted")

    bpy.ops.preferences.addon_disable(module=PKG)
    check(all(n.text is not None for _t, n in notes), "disabling the add-on reattaches fallback text")


try:
    main()
except Exception:
    traceback.print_exc()
    failures.append("exception")

print(f"\n{'FAILED: ' + str(len(failures)) if failures else 'ALL SMOKE CHECKS PASSED'}")
sys.stdout.flush()
os._exit(1 if failures else 0)
