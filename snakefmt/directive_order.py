"""
Custom directive orders: parsing, validation and printing.

The default order of directives is the order of the specs in `snakefmt.parser.grammar`,
which stays the source of truth. There is one order for the directives of rules (also
checkpoints and `use rule ... with:`) and one for those of modules. When given, an
order must list every directive of its block type.
"""

import json
from dataclasses import dataclass
from typing import Any, Optional, Sequence

import click

from snakefmt.parser.grammar import SnakeModule, SnakeRule, SnakeUseRule

# Directives that run something. Snakemake allows a single action per rule and no
# directive may follow it, so the actions always come last.
ACTION_DIRECTIVES = frozenset(SnakeRule.spec).difference(SnakeUseRule.spec)


@dataclass(frozen=True)
class DirectiveOrderOption:
    """A directive order option: the block type it applies to and how to set it."""

    config_key: str
    flag: str
    block: str
    default: tuple[str, ...]
    # directives that always come last, so can't be part of the order
    actions: frozenset[str] = frozenset()

    def toml(self, order: Sequence[str]) -> str:
        return f"{self.config_key} = {json.dumps(list(order))}"

    def command_line(self, order: Sequence[str]) -> str:
        return f"{self.flag} {','.join(order)}"

    def complete(self, order: Sequence[str]) -> list[str]:
        """`order` followed by the missing directives, in default order."""
        return [*order, *(name for name in self.default if name not in order)]

    def validate(self, order: Sequence[str]) -> None:
        """Raises a ValueError describing the first problem with `order`."""
        seen = set()
        for name in order:
            if name in self.actions:
                raise ValueError(
                    f"'{name}' is an action directive and cannot be part of the "
                    "directive order: Snakemake allows only one action per rule and "
                    "no directive may follow it, so actions are always sorted last"
                )
            if name not in self.default:
                raise ValueError(
                    f"unknown {self.block} directive '{name}'; valid {self.block} "
                    f"directives are: {', '.join(self.default)}"
                )
            if name in seen:
                raise ValueError(f"directive '{name}' is listed more than once")
            seen.add(name)

        missing = [name for name in self.default if name not in seen]
        if missing:
            raise ValueError(
                f"incomplete directive order, missing {self.block} directives: "
                f"{', '.join(missing)}\n\n"
                "Adding them in default order after yours gives:\n\n"
                + format_orders([(self, self.complete(order))])
            )


RULE_ORDER = DirectiveOrderOption(
    "directive_order",
    "--directive-order",
    "rule",
    tuple(SnakeUseRule.ordered()),
    ACTION_DIRECTIVES,
)
MODULE_ORDER = DirectiveOrderOption(
    "module_directive_order",
    "--module-directive-order",
    "module",
    tuple(SnakeModule.ordered()),
)


def format_orders(orders: Sequence[tuple[DirectiveOrderOption, Sequence[str]]]) -> str:
    """The orders as lines for the config file and as command line options."""
    toml = "\n".join(option.toml(order) for option, order in orders)
    command_line = " ".join(option.command_line(order) for option, order in orders)
    return (
        f"# pyproject.toml, under [tool.snakefmt]:\n{toml}\n\n"
        f"# command line:\n{command_line}"
    )


def format_effective_orders(
    directive_order: Optional[Sequence[str]],
    module_directive_order: Optional[Sequence[str]],
) -> str:
    """The orders in effect: the custom orders if given, else the default ones."""
    return format_orders(
        [
            (RULE_ORDER, directive_order or RULE_ORDER.default),
            (MODULE_ORDER, module_directive_order or MODULE_ORDER.default),
        ]
    )


class DirectiveOrderType(click.ParamType):
    """
    A comma-separated string on the command line, or an array of strings in
    the configuration file. Converts to a validated tuple of directive names.
    """

    name = "directive_order"

    def __init__(self, option: DirectiveOrderOption) -> None:
        self.option = option

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
        if directive_order:  # nothing given means the default order
            try:
                self.option.validate(directive_order)
            except ValueError as error:
                self.fail(str(error), param, ctx)
        return directive_order
