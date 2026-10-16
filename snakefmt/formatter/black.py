import re
from tokenize import TokenInfo
from typing import Literal

import black.parsing

from snakefmt.config import Mode
from snakefmt.exceptions import InvalidPython
from snakefmt.parser.tokens import TAB, extract_line_indent


def format_python(
    raw: str,
    mode: Mode,
    indent=0,
    partial: Literal["", ":", "("] = "",
    start_token: TokenInfo | None = None,
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
        safe_indent = max(extract_line_indent(line) for line in raw.splitlines())
        string = raw + f"{safe_indent} pass"
    elif partial == "(":
        # Tb() effects equals to a entire new indent
        string = " " * indent + "Tb(\n" + raw + "\n)"
    else:
        string = raw
    try:
        fmted = black.format_str(prefix + string, mode=mode)
    except black.parsing.InvalidInput as e:
        if start_token is not None:
            match = re.search(r"(Cannot parse.*?:\s*)(?P<line>\d+)(.*)", str(e))
            if match:
                err_msg = match.group(1) + str(start_token.start[0]) + match.group(3)
            else:
                err_msg = str(e)
        else:
            err_msg = str(e)
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
            if "#" not in fix:  # safe to unpack function
                fix = TAB * (indent + 1) + fix[3:-1] + "\n"
            else:
                fix = (
                    format_python(raw + "\n#", mode, indent, partial).rsplit("\n", 2)[0]
                    + "\n"
                )
    return fix
