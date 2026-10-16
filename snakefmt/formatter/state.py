import re
from typing import NamedTuple

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
