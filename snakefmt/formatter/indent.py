from typing import Iterable

TAB = "    "  # PEP8, indentation will be coded as 4 spaces


def deindent_lines(old_indent: str, target_indent_level: int, lines: Iterable[str]):
    """Reindent lines to a new level, stripping the old indent if present."""
    target_indent = TAB * target_indent_level
    return [
        target_indent + line[len(old_indent) :] if line.startswith(old_indent) else line
        for line in lines
    ]


def replace_leading_tabs(line: str) -> str:
    """Expand tabs in the leading whitespace of ``line`` to four spaces.

    Only the indentation of the first physical line is touched, so tabs inside
    string literal content (which may be merged into the same string) stay
    verbatim.
    """
    end = 0
    while end < len(line) and line[end] in " \t":
        end += 1
    return line[:end].replace("\t", TAB) + line[end:]
