import re
import tokenize
from tokenize import TokenInfo
from typing import Literal

import black.parsing

from snakefmt.config import Mode
from snakefmt.exceptions import InvalidPython
from snakefmt.formatter.indent import TAB
from snakefmt.parser.tokens import extract_line_indent, splitlines


def _contains_comment(text: str) -> bool:
    """Whether ``text`` contains a comment token (not merely a ``#`` in a string)."""
    try:
        tokens = tokenize.generate_tokens(splitlines(text).__next__)
        return any(token.type == tokenize.COMMENT for token in tokens)
    except (tokenize.TokenError, IndentationError):
        return False


def format_python(
    raw: str,
    mode: Mode,
    indent=0,
    partial: Literal["", ":", "(", "#"] = "",
    start_token: TokenInfo | None = None,
    line_map: list[int | None] | None = None,
) -> str:
    """Format a string using Black formatter.

    if indent:
        prefix = make series of `{' ' * i}if 1:\n` to increase indent level
        format(prefix + string)
        remove first `indent` lines
    if partial == ":":
        safe_indent = longest(prefix spacing)
        format(string + f"\n{safe_indent} pass")
        remove the last line
    if partial == "(":
        format("f(" + string + ")")
        if string.startswith("f(\n"):
            remove the first line and the last line
        else:
            remove first three characters and the last character
    """
    prefix = ""
    for i in range(indent):
        prefix += " " * i + "def a():\n"
    if partial == ":":
        # for block such as if/else/...
        safe_indent = max(extract_line_indent(line) for line in splitlines(raw))
        string = raw + f"{safe_indent} pass"
    elif partial == "(":
        # Tb() effects equals to a entire new indent
        string = " " * indent + "Tb(\n" + raw + "\n)"
    elif partial == "#":
        string = "if 1:" + "".join(raw).rstrip("\n") + "\n   ..."
    else:
        string = raw
    try:
        fmted = black.format_str(prefix + string, mode=mode)
    except black.parsing.InvalidInput as e:
        err_msg = str(e)
        # Not clear whether all Black errors start with 'Cannot parse' - it seems to
        # in the tests I ran
        match = re.search(r"(Cannot parse.*?:\s*)(?P<line>\d+)(.*)", err_msg)
        if match:
            line = int(match.group("line"))
            if start_token is not None:
                mapped = start_token.start[0]
            else:
                mapped = None
                if line_map is not None:
                    if 0 < line <= len(line_map):
                        mapped = line_map[line - 1]
                    elif line == len(line_map) + 1:
                        # Black reports EOF one line past the last line.
                        for index in range(len(line_map) - 1, -1, -1):
                            line_index = line_map[index]
                            if line_index is not None:
                                mapped = line_index + (line - index - 1)
                                break
            if mapped is not None:
                err_msg = match.group(1) + str(mapped) + match.group(3)
        err_msg += (
            "\n\n(Note reported line number may be incorrect, as"
            " snakefmt could not determine the true line number)"
        )
        err_msg = f"Black error:\n```\n{str(err_msg)}\n```\n"
        raise InvalidPython(err_msg) from None
    if indent:
        fix = fmted.split("\n", indent)[-1]
    else:
        fix = fmted
    if partial == ":":
        fix = fix.rstrip().rsplit("\n", 1)[0] + "\n"
    elif partial == "(":
        fix = fix.strip()
        if fix.startswith("Tb(\n"):
            fix = fix.split("\n", 1)[1].rsplit("\n", 1)[0] + "\n"
        else:
            if not _contains_comment(fix):  # safe to unpack function
                fix = TAB * (indent + 1) + fix[3:-1] + "\n"
            else:
                fix = (
                    format_python(raw + "\n#", mode, indent, partial).rsplit("\n", 2)[0]
                    + "\n"
                )
    elif partial == "#":
        fake_fmt = fix.strip()
        fix = fake_fmt.split(":", 1)[1].rsplit("\n", 1)[0] + "\n"
    return fix
