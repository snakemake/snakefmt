from typing import Iterable

TAB = "    "  # PEP8, indentation will be coded as 4 spaces


def deindent_lines(old_indent: str, target_indent_level: int, lines: Iterable[str]):
    """Reindent lines to a new level, stripping the old indent if present."""
    target_indent = TAB * target_indent_level
    return [
        target_indent + line[len(old_indent) :] if line.startswith(old_indent) else line
        for line in lines
    ]
