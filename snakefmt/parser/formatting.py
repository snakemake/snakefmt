import re
from tokenize import TokenInfo
from typing import Literal, NamedTuple

import black.parsing

from snakefmt.config import Mode
from snakefmt.exceptions import InvalidPython
from snakefmt.parser.tokens import TAB, extract_line_indent

_FMT_DIRECTIVE_RE = re.compile(
    r"^# fmt: (off|on)(?:\[(\w+(?:,\s*\w+)*)\])?(?=$|\s{2}|\s#)"
)


class FormatState(NamedTuple):
    fmt_on: bool = True
    sort_directives: bool | None = None
    skip_next: bool = False  # one-time directive for the next snakemake block
    format_shell: bool = False
    # custom directive order overriding the default `subautomata` order;
    # empty means "use the default order". Directives missing from the custom
    # list keep their default (subautomata) position, which puts actions last.
    rule_order: tuple[str, ...] = ()
    module_order: tuple[str, ...] = ()

    @property
    def not_format(self):
        return not self.fmt_on or self.skip_next

    def update(self, comment: str):
        """check single line comment line for pattern:
        ```
        # fmt: off
        # fmt: off[option1, option2, ...]
        # fmt: on
        # fmt: on[option1, option2, ...]
        ```

        Currently, options can be:
        - sort: whether to sort snakemake directives (e.g. input, output, params, etc.)
        - next: whether to apply the directive to the next snakemake block only
            Do not effect blocks after empty lines.
            Cannot be disabled by `# fmt: on[next]`
        - only the first directive will be applied

        If found `# fmt: on` and no `# fmt: off` before:
            if `fmt: off[sort]` is False:
                    sort_directives == True  -> enabled
                    sort_directives == False -> disabled in this indent before
                    sort_directives == None  -> haven't enabled originally
                turn it on
        """
        if match := _FMT_DIRECTIVE_RE.match(comment):
            directive, options = match.groups()
            # Parse options: "sort,next" -> ["sort", "next"] -> "sort"
            option = [opt.strip() for opt in (options or "").split(",")][0]
            if not self.fmt_on:  # only check `# fmt: on`
                if directive == "on" and not option:
                    return self._replace(fmt_on=True)
            elif directive == "on":
                if option == "sort":
                    return self._replace(sort_directives=True)
                if self.sort_directives is False:
                    # re-enable sorting if it was disabled by `# fmt: off[sort]` before,
                    # but should effect if no `# fmt: off[sort]` in this indent before.
                    return self._replace(sort_directives=True)
            elif directive == "off":
                if option == "sort":
                    return self._replace(sort_directives=False)
                if option == "next":
                    return self._replace(skip_next=True)
                return self._replace(fmt_on=False)
        return self

    def consume_skip_next(self) -> "FormatState":
        """Returns new state with skip_next consumed (set to False)"""
        if self.skip_next:
            return self._replace(skip_next=False)
        return self

    @staticmethod
    def found_skip(comment: str):
        return "# fmt: skip" in comment

    def reset_sort(self):
        if self.sort_directives is False:
            return self._replace(sort_directives=None)
        return self


def format_black(
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
                    format_black(raw + "\n#", mode, indent, partial).rsplit("\n", 2)[0]
                    + "\n"
                )
    return fix
