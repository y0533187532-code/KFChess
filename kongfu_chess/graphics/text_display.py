"""Prepare mixed Hebrew/Latin strings for OpenCV's left-to-right text renderer."""

from __future__ import annotations

import re

_HEBREW_CHAR = re.compile(r"[\u0590-\u05FF]")
_SEGMENT = re.compile(
    r"[\u0590-\u05FF]+"
    r"|[a-h][0-9]+(?:->[a-h][0-9]+)?"
    r"|[0-9]+(?:\.[0-9]+)?s?"
    r"|[A-Za-z]+"
    r"|\s+"
    r"|[^\u0590-\u05FF0-9A-Za-z\s]+"
)
_LTR_ALNUM = re.compile(r"^[A-Za-z0-9]+$")
_CHESS_MOVE = re.compile(r"^[a-h][0-9]+(?:->[a-h][0-9]+)?$")


def contains_hebrew(text: str) -> bool:
    return _HEBREW_CHAR.search(text) is not None


def prepare_opencv_display_text(text: str, *, rtl: bool) -> str:
    """Reverse Hebrew runs and segment order so putText reads naturally in RTL."""
    if not rtl or not contains_hebrew(text):
        return text
    segments: list[str] = []
    for match in _SEGMENT.finditer(text):
        segments.append(match.group(0))
    segments = _coalesce_ltr_segments(segments)
    prepared: list[str] = []
    for segment in segments:
        if contains_hebrew(segment):
            prepared.append(segment[::-1])
        else:
            prepared.append(segment)
    return "".join(reversed(prepared))


def _coalesce_ltr_segments(segments: list[str]) -> list[str]:
    """Keep Latin letters, digits, and chess coords together for display."""
    merged: list[str] = []
    buffer = ""
    for segment in segments:
        if _LTR_ALNUM.match(segment) or _CHESS_MOVE.match(segment):
            buffer += segment
            continue
        if buffer:
            merged.append(buffer)
            buffer = ""
        merged.append(segment)
    if buffer:
        merged.append(buffer)
    return merged
