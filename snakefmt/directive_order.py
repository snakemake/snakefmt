"""
Custom directive orders: parsing, validation and printing.

The default order of directives is the order in which the parser blocks are
registered (`snakefmt.parser`), which stays the source of truth. There is one order
for the directives of rules (also checkpoints and `use rule ... with:`) and one for
those of modules. When given, an order must list every directive of its block type.
"""

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any, Optional, Sequence

import click

from snakefmt.parser.grammar import Module, Rule, UseRule

# Directives that run something. Snakemake allows a single action per rule and no
# directive may follow it, so the actions always come last.
ACTION_DIRECTIVES = frozenset(Rule.exec_subautomata)


def quote(names: Sequence[str]) -> str:
    return ", ".join(f"'{name}'" for name in names)


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
        """
        The valid directives of `order`, at their first occurrence, followed by the
        missing directives in default order.
        """
        listed = [name for name in dict.fromkeys(order) if name in self.default]
        return [*listed, *(name for name in self.default if name not in listed)]

    def validate(self, order: Sequence[str]) -> None:
        """
        Raises a ValueError listing all the problems of `order`: action directives,
        unknown directives, directives listed more than once and missing directives.
        """
        actions = [name for name in dict.fromkeys(order) if name in self.actions]
        unknown = [
            name
            for name in dict.fromkeys(order)
            if name not in self.default and name not in self.actions
        ]
        counts = Counter(name for name in order if name in self.default)
        repeated = [name for name, count in counts.items() if count > 1]
        missing = [name for name in self.default if name not in counts]

        problems = []
        if actions:
            problems.append(
                "action directives are not allowed in the directive order: "
                f"{quote(actions)} (Snakemake allows only one action per rule and no "
                "directive may follow it, so actions are always sorted last)"
            )
        if unknown:
            problems.append(
                f"unknown {self.block} directives: {quote(unknown)} (valid "
                f"{self.block} directives are: {', '.join(self.default)})"
            )
        if repeated:
            problems.append(f"directives listed more than once: {quote(repeated)}")

        if not problems and not missing:
            return
        completed = format_orders([(self, self.complete(order))])
        missing_problem = f"missing {self.block} directives: {', '.join(missing)}"
        if not problems:
            raise ValueError(
                f"incomplete directive order, {missing_problem}\n\n"
                f"Adding them in default order after yours gives:\n\n{completed}"
            )
        if missing:
            problems.append(missing_problem)
        listed_problems = "".join(f"\n- {problem}" for problem in problems)
        raise ValueError(
            f"invalid directive order:{listed_problems}\n\n"
            "A valid order based on yours, with the invalid directives removed and "
            f"the missing ones added in default order, is:\n\n{completed}"
        )


RULE_ORDER = DirectiveOrderOption(
    "directive_order",
    "--directive-order",
    "rule",
    tuple(UseRule.subautomata),
    ACTION_DIRECTIVES,
)
MODULE_ORDER = DirectiveOrderOption(
    "module_directive_order",
    "--module-directive-order",
    "module",
    tuple(Module.subautomata),
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
            names = list(value)
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
