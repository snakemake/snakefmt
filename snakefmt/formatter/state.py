import re
from typing import TYPE_CHECKING, NamedTuple

from snakefmt.config import Mode
from snakefmt.formatter import black

if TYPE_CHECKING:
    from snakefmt.parser.snakefile import Snakefile

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

    def format(self, snakefile: "Snakefile", mode: Mode) -> str:
        """Format a parsed `Snakefile` under this state."""
        from snakefmt.formatter.segments import format_segments

        # if set to None, it will not be enabled by `# fmt: on`
        python_codes: list[str] = []
        snakemake_codes: list[tuple[str, str]] = []
        last_str = ""
        for segment, indent_proxy in format_segments(snakefile, mode, self):
            if indent_proxy is not None:
                python_codes.append(last_str)
                last_str = ""
                snakemake_codes.append((segment, indent_proxy))
            else:
                last_str += segment
        placeholder = "o" * 50
        raw_str = "".join(python_codes) + last_str
        while placeholder in raw_str:
            placeholder *= 2
        raw_str = "#\n"
        for python_code, (snakemake_code, indent) in zip(python_codes, snakemake_codes):
            if snakemake_code.count("\n") == 1:  # must at the end of line
                snakemake_proxy = f"{indent}def l{placeholder}1ng(): ...\n"
            else:
                snakemake_proxy = f"{indent}def l{placeholder}ng():\n{indent} return\n"
            raw_str += python_code + snakemake_proxy
        raw_str += last_str
        formatted, *formatted_split = black.format_python(raw_str, mode).split(
            placeholder
        )
        final_str = formatted
        for formatted, (snakemake_code, _) in zip(formatted_split, snakemake_codes):
            final_str = final_str.rsplit("\n", 1)[0] + "\n" + snakemake_code
            if formatted.startswith("1"):
                final_str += formatted.split("\n", 1)[-1]
            else:
                final_str += formatted.split("\n", 2)[-1]
        return final_str[1:].lstrip("\n")
