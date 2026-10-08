# SPDX-FileCopyrightText: 2026 Brandon Gutowski
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pawst_its"))

from text_layout import (  # noqa: E402
    Line,
    TextBuffer,
    caret_limit,
    hit_test,
    line_index,
    next_word,
    prev_word,
    wrap,
)


def mono(s):
    """Monospace measure: every character is 1 unit wide."""
    return float(len(s))


def texts(text, lines):
    return [text[l.start:l.end] for l in lines]


def test_empty_text_has_one_line():
    assert wrap("", 10, mono) == [Line(0, 0, False)]


def test_short_text_single_line():
    assert texts("hello", wrap("hello", 10, mono)) == ["hello"]


def test_word_wrap_keeps_trailing_space_on_previous_line():
    text = "hello world again"
    lines = wrap(text, 11, mono)
    assert texts(text, lines) == ["hello world ", "again"]
    assert lines[0].soft and not lines[1].soft


def test_hard_newlines_and_blank_lines():
    text = "a\n\nb"
    lines = wrap(text, 10, mono)
    assert texts(text, lines) == ["a", "", "b"]
    assert [l.start for l in lines] == [0, 2, 3]


def test_trailing_newline_gives_empty_last_line():
    text = "abc\n"
    lines = wrap(text, 10, mono)
    assert texts(text, lines) == ["abc", ""]
    assert line_index(lines, 4) == 1


def test_long_word_hard_breaks():
    text = "abcdefghij"
    lines = wrap(text, 4, mono)
    assert texts(text, lines) == ["abcd", "efgh", "ij"]


def test_long_word_after_short_word():
    text = "hi abcdefghij"
    assert texts(text, wrap(text, 4, mono)) == ["hi ", "abcd", "efgh", "ij"]


def test_wrap_positions_cover_text():
    text = "the quick brown fox\njumps over the lazy dog"
    lines = wrap(text, 7, mono)
    rebuilt = ""
    for i, l in enumerate(lines):
        rebuilt += text[l.start:l.end]
        if not l.soft and i < len(lines) - 1:
            rebuilt += "\n"
    assert rebuilt == text


def test_line_index_soft_boundary_goes_to_next_line():
    text = "hello world"
    lines = wrap(text, 6, mono)
    assert texts(text, lines) == ["hello ", "world"]
    assert line_index(lines, 6) == 1
    assert line_index(lines, 5) == 0
    assert caret_limit(lines[0]) == 5


def test_hit_test():
    text = "hello"
    line = wrap(text, 10, mono)[0]
    assert hit_test(text, line, 0.0, mono) == 0
    assert hit_test(text, line, 2.4, mono) == 2
    assert hit_test(text, line, 99, mono) == 5


def test_word_boundaries():
    s = "foo  bar baz"
    assert prev_word(s, len(s)) == 9
    assert prev_word(s, 9) == 5
    assert next_word(s, 0) == 5
    assert next_word(s, 5) == 9


def test_buffer_insert_backspace_delete():
    b = TextBuffer("ac")
    b.caret = 1
    b.insert("b")
    assert b.text == "abc" and b.caret == 2
    b.backspace()
    assert b.text == "ac" and b.caret == 1
    b.delete_forward()
    assert b.text == "a" and b.caret == 1
    b.backspace()
    b.backspace()
    assert b.text == "" and b.caret == 0


def test_buffer_word_delete():
    b = TextBuffer("hello big world")
    b.backspace(word=True)
    assert b.text == "hello big "
    b.caret = 0
    b.delete_forward(word=True)
    assert b.text == "big "


def test_buffer_selection_replace_and_cut():
    b = TextBuffer("hello world")
    b.caret = 0
    b.right(extend=True, word=True)
    assert b.selected_text() == "hello "
    b.insert("bye ")
    assert b.text == "bye world"
    b.select_all()
    assert b.cut() == "bye world"
    assert b.text == "" and not b.has_selection()


def test_left_right_collapse_selection():
    b = TextBuffer("abcdef")
    b.caret = 2
    b.right(extend=True)
    b.right(extend=True)
    assert b.selection() == (2, 4)
    b.left()
    assert b.caret == 2 and not b.has_selection()


def test_home_end_and_vertical_motion():
    text = "abc\nabcdef\nab"
    b = TextBuffer(text)
    lines = wrap(text, 20, mono)
    b.caret = 9  # line 1, col 5
    b.vertical(lines, mono, -1)
    assert b.caret == 3  # clamped to end of "abc"
    b.vertical(lines, mono, 1)
    assert b.caret == 9  # goal column remembered
    b.vertical(lines, mono, 1)
    assert b.caret == len(text)
    b.home(lines)
    assert b.caret == 11
    b.vertical(lines, mono, 1)
    assert b.caret == len(text)
    b.caret = 5
    b.vertical(lines, mono, -1)
    b.vertical(lines, mono, -1)
    assert b.caret == 0
    b.end(lines)
    assert b.caret == 3


if __name__ == "__main__":
    # Allows running without pytest: python3 tests/test_text_layout.py
    tests = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_")]
    for name, fn in tests:
        fn()
        print("ok  ", name)
    print(f"{len(tests)} passed")
