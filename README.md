# Pawst-Its for Blender

Cat-themed, Houdini-style sticky notes for every node editor: shader, geometry nodes, compositor, texture and custom trees.

- **Shift+P** drops a note at the mouse cursor and you start typing right away.
- **Double-click** a note to edit it again.
- Finish with **Esc**, **Ctrl+Enter**, or a click outside the note.

Each note has a **name**, a **color** and a cat **style**:
- **Cat Head**: pointy ears and whiskers
- **Peeking Cat**: a black cat peeking over the top, its round rear end and tail hanging off the bottom
- **Paw Print**: a chubby paw with claws and toe beans; the text sits on a pink pad
- **Cat Loaf**: a loaf cat seen from the side: big-eared head on the left, belly running straight into a tail curled up its back
- **Kitty Tail**: a stretched-out cat whose slim front leg hangs down like a speech-bubble pointer, tail held high

Requires Blender 4.2 or newer.

## Install

```sh
mkdir -p dist && blender --command extension build --source-dir pawst_its --output-dir dist
```

Then in Blender, go to *Edit > Preferences > Get Extensions*, open the ▾ menu, choose *Install from Disk…* and pick `dist/pawst_its-2.3.0.zip`.

Upgrading from "Sticky Notes" 1.x: uninstall it first (both use Shift+P). Notes in your existing files convert automatically when you open them, keeping their text, name, color and size. Retired styles become Cat Head.

## Using it

| Action | How |
|---|---|
| New note | **Shift+P** over the canvas, or *Add > Layout > Pawst-It* |
| Edit text | Double-click the note, the right-click menu, or the sidebar's **Edit Text** |
| Name, color, style, font size | Sidebar (**N**) > **Pawst-Its** tab, or the right-click menu |
| Outline (stroke) | Sidebar > **Stroke**, then pick a **Stroke Color**: handy on themes where notes are hard to see. Turn it on for all new notes in the add-on preferences |
| Move / resize / delete / duplicate | Same as any Frame node (G, drag the edges, X, Shift+D) |

While typing:
- Enter adds a new line.
- Ctrl+A / C / X / V select all, copy, cut and paste.
- Arrow keys, Home and End move the caret; Shift extends the selection.
- Ctrl (or ⌥ on macOS) + Backspace or Arrow works a word at a time.
- Mouse-drag selects text.
- Middle mouse and the scroll wheel still pan and zoom.
- Any other shortcut (Ctrl+S, Ctrl+Z, …) finishes editing and then runs normally.

Notes grow to fit their text unless you turn off **Auto Height**. You can rebind the keys under *Preferences > Keymap > Node Editor*. Default color, style and size are in the add-on's preferences.

## How it works

Each note is an ordinary **Frame node**, which is why moving, selecting, undo, copy/paste and node groups all work as usual.
- The name is the frame's label.
- The body text lives in a hidden Text datablock (`.PawstIt…`) that the add-on manages for you.

When you save, each frame is linked to its Text. Anyone opening the file *without* the add-on still sees every note as a regular frame with its text.

Pawst-Its are drawn on top of your nodes, like a sticky note stuck to the screen, so they're always readable. A node sitting underneath a note is hidden until you move one of them.

## Tests

```sh
python3 tests/test_text_layout.py   # wrapping / caret logic, no Blender needed
python3 tests/test_shapes.py        # every style hides the frame; no sharp corners or border
tests/run_smoke.sh                  # builds the extension, runs it headless in an isolated Blender profile
```

## License

Pawst-Its is free software, released under the [GNU General Public License v3.0 or later](LICENSE), the same license Blender add-ons use.
