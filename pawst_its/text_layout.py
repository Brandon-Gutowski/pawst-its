# SPDX-FileCopyrightText: 2026 Brandon Gutowski
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Pure-Python text wrapping and editing model for Pawst-Its.

Nothing in here imports bpy, so it can be unit-tested outside Blender.
Every width is measured by a caller-supplied ``measure(str) -> float``.
"""

import re
from typing import Callable, List, NamedTuple, Optional, Tuple

Measure = Callable[[str], float]

_TOKEN = re.compile(r"\S+\s*|\s+")


class Line(NamedTuple):
    start: int  # index into the full text
    end: int  # exclusive; never includes the '\n'
    soft: bool  # True when the line was broken by wrapping, not by '\n'


def wrap(text: str, max_width: float, measure: Measure) -> List[Line]:
    """Word-wrap ``text`` to ``max_width``. Always returns at least one line."""
    lines: List[Line] = []
    offset = 0
    for para in text.split("\n"):
        _wrap_para(para, offset, max_width, measure, lines)
        offset += len(para) + 1
    return lines


def _wrap_para(para, offset, max_width, measure, out):
    if not para:
        out.append(Line(offset, offset, False))
        return
    line_start = 0
    line_end = 0
    for m in _TOKEN.finditer(para):
        ts, te = m.start(), m.end()
        if measure(para[line_start:te].rstrip()) <= max_width:
            line_end = te
            continue
        if line_end > line_start:
            out.append(Line(offset + line_start, offset + line_end, True))
            line_start = ts
        # A single word wider than the note: hard-break it by characters.
        while measure(para[line_start:te].rstrip()) > max_width:
            cut = _fit_chars(para, line_start, te, max_width, measure)
            out.append(Line(offset + line_start, offset + cut, True))
            line_start = cut
        line_end = te
    out.append(Line(offset + line_start, offset + line_end, False))


def _fit_chars(s, start, end, max_width, measure):
    """Largest cut in (start, end) such that s[start:cut] fits; at least start + 1."""
    lo, hi = start + 1, end
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if measure(s[start:mid]) <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return lo


def line_index(lines: List[Line], idx: int) -> int:
    """Visual line containing caret position ``idx``.

    At a soft-wrap boundary the caret belongs to the start of the next line.
    """
    found = 0
    for i, line in enumerate(lines):
        if line.start <= idx:
            found = i
        else:
            break
    return found


def caret_limit(line: Line) -> int:
    """Rightmost caret position that still displays on ``line``."""
    return line.end - 1 if line.soft and line.end > line.start else line.end


def hit_test(text: str, line: Line, x: float, measure: Measure) -> int:
    """Caret index on ``line`` closest to horizontal offset ``x``."""
    best, best_d = line.start, abs(x)
    for p in range(line.start + 1, caret_limit(line) + 1):
        d = abs(measure(text[line.start:p]) - x)
        if d < best_d:
            best, best_d = p, d
    return best


def prev_word(text: str, i: int) -> int:
    while i > 0 and text[i - 1].isspace():
        i -= 1
    while i > 0 and not text[i - 1].isspace():
        i -= 1
    return i


def next_word(text: str, i: int) -> int:
    n = len(text)
    while i < n and not text[i].isspace():
        i += 1
    while i < n and text[i].isspace():
        i += 1
    return i


class TextBuffer:
    """Editable text with a caret and an optional selection anchor."""

    def __init__(self, text: str = ""):
        self.text = text
        self.caret = len(text)
        self.anchor: Optional[int] = None
        self.goal_x: Optional[float] = None

    # -- selection -------------------------------------------------------

    def has_selection(self) -> bool:
        return self.anchor is not None and self.anchor != self.caret

    def selection(self) -> Tuple[int, int]:
        if not self.has_selection():
            return self.caret, self.caret
        return min(self.anchor, self.caret), max(self.anchor, self.caret)

    def selected_text(self) -> str:
        a, b = self.selection()
        return self.text[a:b]

    def select_all(self):
        self.anchor = 0
        self.caret = len(self.text)
        self.goal_x = None

    def _move(self, idx: int, extend: bool):
        if extend:
            if self.anchor is None:
                self.anchor = self.caret
        else:
            self.anchor = None
        self.caret = max(0, min(idx, len(self.text)))

    # -- editing ---------------------------------------------------------

    def _delete_range(self, a: int, b: int):
        self.text = self.text[:a] + self.text[b:]
        self.caret = a
        self.anchor = None
        self.goal_x = None

    def insert(self, s: str):
        a, b = self.selection()
        self.text = self.text[:a] + s + self.text[b:]
        self.caret = a + len(s)
        self.anchor = None
        self.goal_x = None

    def backspace(self, word: bool = False):
        if self.has_selection():
            self._delete_range(*self.selection())
        elif self.caret > 0:
            start = prev_word(self.text, self.caret) if word else self.caret - 1
            self._delete_range(start, self.caret)

    def delete_forward(self, word: bool = False):
        if self.has_selection():
            self._delete_range(*self.selection())
        elif self.caret < len(self.text):
            end = next_word(self.text, self.caret) if word else self.caret + 1
            self._delete_range(self.caret, end)

    def cut(self) -> str:
        s = self.selected_text()
        if s:
            self._delete_range(*self.selection())
        return s

    # -- caret motion ----------------------------------------------------

    def left(self, extend: bool = False, word: bool = False):
        self.goal_x = None
        if self.has_selection() and not extend:
            self._move(self.selection()[0], False)
        else:
            self._move(prev_word(self.text, self.caret) if word else self.caret - 1, extend)

    def right(self, extend: bool = False, word: bool = False):
        self.goal_x = None
        if self.has_selection() and not extend:
            self._move(self.selection()[1], False)
        else:
            self._move(next_word(self.text, self.caret) if word else self.caret + 1, extend)

    def home(self, lines: List[Line], extend: bool = False):
        self.goal_x = None
        self._move(lines[line_index(lines, self.caret)].start, extend)

    def end(self, lines: List[Line], extend: bool = False):
        self.goal_x = None
        self._move(caret_limit(lines[line_index(lines, self.caret)]), extend)

    def vertical(self, lines: List[Line], measure: Measure, delta: int, extend: bool = False):
        i = line_index(lines, self.caret)
        if self.goal_x is None:
            self.goal_x = measure(self.text[lines[i].start:self.caret])
        j = i + delta
        if j < 0:
            target = 0
        elif j >= len(lines):
            target = len(self.text)
        else:
            target = hit_test(self.text, lines[j], self.goal_x, measure)
        goal = self.goal_x
        self._move(target, extend)
        self.goal_x = goal

    def click(self, idx: int, extend: bool = False):
        self.goal_x = None
        self._move(idx, extend)
