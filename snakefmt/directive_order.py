"""
Custom directive order: parsing, validation and merging with the default order.

The default order of directives is the order of the specs in `snakefmt.parser.grammar`,
which stays the source of truth. A custom order is a (partial) list of directive names
that are sorted first, in the order given.
"""

from typing import Any, Optional, Sequence

import click

from snakefmt.parser.grammar import SnakeModule, SnakeRule, SnakeUseRule

# Directives that run something. Snakemake allows a single action per rule and no
# directive may follow it, so the actions always come last.
ACTION_DIRECTIVES = frozenset(SnakeRule.spec).difference(SnakeUseRule.spec)

# Directive names that can be reordered, in default order.
# Rule directives first, then those that only modules have.
SORTABLE_DIRECTIVES = [
    *SnakeUseRule.ordered(),
    *(name for name in SnakeModule.ordered() if name not in SnakeUseRule.spec),
]


def validate_directive_order(directive_order: Sequence[str]) -> None:
    """Raises a ValueError naming the first entry that is not a valid directive."""
    seen = set()
    for name in directive_order:
        if name in ACTION_DIRECTIVES:
            raise ValueError(
                f"'{name}' is an action directive and cannot be part of the directive "
                "order: Snakemake allows only one action per rule and no directive "
                "may follow it, so actions are always sorted last"
            )
        if name not in SORTABLE_DIRECTIVES:
            raise ValueError(
                f"unknown directive '{name}'; valid directives are: "
                f"{', '.join(SORTABLE_DIRECTIVES)}"
            )
        if name in seen:
            raise ValueError(f"directive '{name}' is listed more than once")
        seen.add(name)


def effective_directive_order(directive_order: Sequence[str] = ()) -> list[str]:
    """
    The order that results from merging `directive_order` with the default order,
    as a single list that applies to both rules and modules: rule directives in the
    order rules sort them, with the module-only directives added around them so that
    modules sort theirs in the order modules do.
    Using the result as `directive_order` gives the same sorting as `directive_order`.
    """
    rule_order = [
        name
        for name in SnakeRule.ordered(directive_order)
        if name not in ACTION_DIRECTIVES
    ]
    module_order = SnakeModule.ordered(directive_order)

    effective: list[str] = []
    for name in rule_order:
        if name in module_order:
            # module-only directives that module sorting places before this one
            before = module_order[: module_order.index(name)]
            effective.extend(
                other
                for other in before
                if other not in rule_order and other not in effective
            )
        effective.append(name)
    effective.extend(name for name in module_order if name not in effective)
    return effective


class DirectiveOrderType(click.ParamType):
    """
    A comma-separated string on the command line, or an array of strings in
    the configuration file. Converts to a validated tuple of directive names.
    """

    name = "directive_order"

    def convert(
        self, value: Any, param: Optional[click.Parameter], ctx: Optional[click.Context]
    ) -> tuple[str, ...]:
        if isinstance(value, str):
            names = value.split(",")
        elif isinstance(value, (list, tuple)) and all(
            isinstance(name, str) for name in value
        ):
            names = value
        else:
            self.fail(
                "the directive order must be a comma-separated string or an array of "
                f"strings, not {value!r}",
                param,
                ctx,
            )
        directive_order = tuple(name.strip() for name in names if name.strip())
        try:
            validate_directive_order(directive_order)
        except ValueError as error:
            self.fail(str(error), param, ctx)
        return directive_order
