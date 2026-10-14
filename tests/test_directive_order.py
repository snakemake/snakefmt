"""Tests for custom directive orders (issue #318):
``-o/--directive-order`` and ``-m/--module-directive-order`` (and their config
options) and ``-p/--print-directive-order``.
"""

import json
import re
import shlex
import tomllib
from pathlib import Path

import pytest

from snakefmt.blocken import Module, Rule, UseRule
from snakefmt.directive_order import ACTION_DIRECTIVES as GRAMMAR_ACTIONS
from snakefmt.directive_order import MODULE_ORDER, RULE_ORDER
from snakefmt.snakefmt import main
from snakefmt.blocken import TAB
from tests import setup_formatter
from tests.directive_order_fixtures import (
    ACTION_DIRECTIVES,
    ACTION_REASON,
    CUSTOM_BOTH_PRINT,
    CUSTOM_MODULE_ORDER,
    CUSTOM_MODULE_ORDER_ARG,
    CUSTOM_MODULE_PRINT,
    CUSTOM_RULE_ORDER,
    CUSTOM_RULE_ORDER_ARG,
    CUSTOM_RULE_PRINT,
    DEFAULT_MODULE_ORDER,
    DEFAULT_MODULE_ORDER_ARG,
    DEFAULT_PRINT,
    DEFAULT_RULE_ORDER,
    DEFAULT_RULE_ORDER_ARG,
    INCOMPLETE_MODULE_ORDER_MESSAGE,
    INCOMPLETE_RULE_ORDER_MESSAGE,
    MODULE_CODE,
    MODULE_CUSTOM_ORDER,
    MODULE_DEFAULT_BLOCK,
    MODULE_DEFAULT_ORDER,
    MODULE_UNSORTED,
    MODULE_VALID_NAMES,
    REPEATED_NAMES_RULE_ORDER_MESSAGE,
    RULE_CODE,
    RULE_CUSTOM_ORDER,
    RULE_DEFAULT_BLOCK,
    RULE_DEFAULT_ORDER,
    RULE_UNSORTED,
    RULE_VALID_NAMES,
    SEVERAL_PROBLEMS_MODULE_ORDER_MESSAGE,
    SEVERAL_PROBLEMS_RULE_ORDER_MESSAGE,
    USE_RULE_CODE,
    USE_RULE_CUSTOM_ORDER,
    USE_RULE_DEFAULT_ORDER,
    VALID_ORDER_INTRO,
)


def format_with_orders(
    snakecode: str, rule_order: tuple = (), module_order: tuple = ()
) -> str:
    formatter = setup_formatter(
        snakecode,
        sort_directives=True,
        directive_order=rule_order,
        module_directive_order=module_order,
    )
    return formatter.get_formatted()


def run_cli(cli_runner, args, stdin=RULE_CODE):
    return cli_runner.invoke(main, [*args, "-"], input=stdin)


def write_config(tmp_path, toml_body: str = "") -> str:
    config = tmp_path / "pyproject.toml"
    config.write_text(f"[tool.snakefmt]\n{toml_body}\n")
    return str(config)


@pytest.fixture
def config(tmp_path) -> str:
    """A config file with no snakefmt settings"""
    return write_config(tmp_path)


def warning_messages(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]


def assert_rejected(result, flags: str, message: str) -> None:
    assert result.exit_code == 2
    assert f"Error: Invalid value for {flags}: {message}\n" in result.stderr


def invalid_order_message(problem: str, completed_block: str) -> str:
    """The message about a complete order with one invalid entry added."""
    return (
        f"invalid directive order:\n- {problem}\n\n"
        f"{VALID_ORDER_INTRO}\n\n{completed_block}"
    )


def action_directive_message(action: str) -> str:
    problem = (
        "action directives are not allowed in the directive order: "
        f"'{action}' {ACTION_REASON}"
    )
    return invalid_order_message(problem, RULE_DEFAULT_BLOCK)


def toml_array(order: tuple) -> str:
    return json.dumps(list(order))


class TestFormatterDirectiveOrder:
    def test_rule_order(self):
        actual = format_with_orders(RULE_CODE, CUSTOM_RULE_ORDER)
        assert actual == RULE_CUSTOM_ORDER

    def test_checkpoint_order(self):
        code = RULE_CODE.replace("rule a:", "checkpoint a:")
        expected = RULE_CUSTOM_ORDER.replace("rule a:", "checkpoint a:")
        assert format_with_orders(code, CUSTOM_RULE_ORDER) == expected

    def test_use_rule_order(self):
        actual = format_with_orders(USE_RULE_CODE, CUSTOM_RULE_ORDER)
        assert actual == USE_RULE_CUSTOM_ORDER

    def test_module_order(self):
        actual = format_with_orders(MODULE_CODE, module_order=CUSTOM_MODULE_ORDER)
        assert actual == MODULE_CUSTOM_ORDER

    def test_no_order_is_the_default_order(self):
        assert format_with_orders(RULE_CODE) == RULE_DEFAULT_ORDER
        assert format_with_orders(USE_RULE_CODE) == USE_RULE_DEFAULT_ORDER
        assert format_with_orders(MODULE_CODE) == MODULE_DEFAULT_ORDER

    def test_module_order_does_not_apply_to_rules(self):
        actual = format_with_orders(RULE_CODE, module_order=CUSTOM_MODULE_ORDER)
        assert actual == RULE_DEFAULT_ORDER
        actual = format_with_orders(USE_RULE_CODE, module_order=CUSTOM_MODULE_ORDER)
        assert actual == USE_RULE_DEFAULT_ORDER

    def test_rule_order_does_not_apply_to_modules(self):
        actual = format_with_orders(MODULE_CODE, rule_order=CUSTOM_RULE_ORDER)
        assert actual == MODULE_DEFAULT_ORDER

    def test_action_stays_last(self):
        code = (
            "rule a:\n"
            f'{TAB}input: "i"\n'
            f'{TAB}message: "m"\n'
            f"{TAB}run:\n"
            f'{TAB * 2}print("hi")\n'
        )
        expected = (
            "rule a:\n"
            f"{TAB}message:\n"
            f'{TAB * 2}"m"\n'
            f"{TAB}input:\n"
            f'{TAB * 2}"i",\n'
            f"{TAB}run:\n"
            f'{TAB * 2}print("hi")\n'
        )
        assert format_with_orders(code, CUSTOM_RULE_ORDER) == expected

    def test_fmt_off_sort_regions_keep_their_original_order(self):
        code = (
            "rule all:\n"
            " params: p=1\n"
            " resources: mem_mb=100\n"
            " threads: 4\n"
            " conda: 'env.yaml'\n"
            " message: 'finishing'\n"
            " # fmt: off[sort]\n"
            " log: 'log.txt'\n"
            " output: 'out.txt'\n"
            " # fmt: on[sort]\n"
            " # Important input\n"
            " input: 'in.txt'\n"
            " name: 'myrule'\n"
            " shell: 'echo done'\n"
        )
        expected = (
            "rule all:\n"
            f"{TAB}message:\n"
            f'{TAB * 2}"finishing"\n'
            f"{TAB}params:\n"
            f"{TAB * 2}p=1,\n"
            f"{TAB}threads: 4\n"
            f"{TAB}conda:\n"
            f'{TAB * 2}"env.yaml"\n'
            f"{TAB}resources:\n"
            f"{TAB * 2}mem_mb=100,\n"
            f"{TAB}# fmt: off[sort]\n"
            f"{TAB}log:\n"
            f'{TAB * 2}"log.txt",\n'
            f"{TAB}output:\n"
            f'{TAB * 2}"out.txt",\n'
            f"{TAB}# fmt: on[sort]\n"
            f"{TAB}# Important input\n"
            f"{TAB}input:\n"
            f'{TAB * 2}"in.txt",\n'
            f"{TAB}name:\n"
            f'{TAB * 2}"myrule"\n'
            f"{TAB}shell:\n"
            f'{TAB * 2}"echo done"\n'
        )
        assert format_with_orders(code, CUSTOM_RULE_ORDER) == expected


class TestDirectiveOrderOptions:
    @pytest.mark.parametrize("flag", ["-o", "--directive-order"])
    def test_rule_order_from_the_command_line(self, cli_runner, tmp_path, flag):
        args = ["--config", write_config(tmp_path), flag, CUSTOM_RULE_ORDER_ARG]
        checkpoint = RULE_CODE.replace("rule a:", "checkpoint a:")
        for code, expected in (
            (RULE_CODE, RULE_CUSTOM_ORDER),
            (checkpoint, RULE_CUSTOM_ORDER.replace("rule a:", "checkpoint a:")),
            (USE_RULE_CODE, USE_RULE_CUSTOM_ORDER),
        ):
            result = run_cli(cli_runner, args, stdin=code)
            assert result.exit_code == 0
            assert result.stdout == expected

    @pytest.mark.parametrize("flag", ["-m", "--module-directive-order"])
    def test_module_order_from_the_command_line(self, cli_runner, tmp_path, flag):
        args = [
            "--config",
            write_config(tmp_path),
            flag,
            CUSTOM_MODULE_ORDER_ARG,
        ]
        result = run_cli(cli_runner, args, stdin=MODULE_CODE)
        assert result.exit_code == 0
        assert result.stdout == MODULE_CUSTOM_ORDER

    def test_rule_order_from_config(self, cli_runner, tmp_path):
        config = write_config(
            tmp_path, f"directive_order = {toml_array(CUSTOM_RULE_ORDER)}"
        )
        for code, expected in (
            (RULE_CODE, RULE_CUSTOM_ORDER),
            (USE_RULE_CODE, USE_RULE_CUSTOM_ORDER),
            (MODULE_CODE, MODULE_DEFAULT_ORDER),
        ):
            result = run_cli(cli_runner, ["--config", config], stdin=code)
            assert result.exit_code == 0
            assert result.stdout == expected

    def test_module_order_from_config(self, cli_runner, tmp_path):
        config = write_config(
            tmp_path, f"module_directive_order = {toml_array(CUSTOM_MODULE_ORDER)}"
        )
        for code, expected in (
            (MODULE_CODE, MODULE_CUSTOM_ORDER),
            (RULE_CODE, RULE_DEFAULT_ORDER),
        ):
            result = run_cli(cli_runner, ["--config", config], stdin=code)
            assert result.exit_code == 0
            assert result.stdout == expected

    def test_command_line_takes_precedence_over_config(self, cli_runner, tmp_path):
        config = write_config(
            tmp_path,
            f"directive_order = {toml_array(DEFAULT_RULE_ORDER)}\n"
            f"module_directive_order = {toml_array(DEFAULT_MODULE_ORDER)}",
        )
        for flag, order, code, expected in (
            ("-o", CUSTOM_RULE_ORDER, RULE_CODE, RULE_CUSTOM_ORDER),
            ("-m", CUSTOM_MODULE_ORDER, MODULE_CODE, MODULE_CUSTOM_ORDER),
        ):
            args = ["--config", config, flag, ",".join(order)]
            assert run_cli(cli_runner, args, stdin=code).stdout == expected

    def test_whitespace_around_names_is_ignored(self, cli_runner, tmp_path):
        order = " , ".join(CUSTOM_RULE_ORDER)
        args = ["--config", write_config(tmp_path), "-o", f" {order} "]
        result = run_cli(cli_runner, args)
        assert result.exit_code == 0
        assert result.stdout == RULE_CUSTOM_ORDER

    @pytest.mark.parametrize("toml_value", ["[]", '""'])
    def test_empty_order_is_the_default_order(self, cli_runner, tmp_path, toml_value):
        config = write_config(
            tmp_path,
            f"directive_order = {toml_value}\nmodule_directive_order = {toml_value}",
        )
        for code, expected in (
            (RULE_CODE, RULE_DEFAULT_ORDER),
            (MODULE_CODE, MODULE_DEFAULT_ORDER),
        ):
            result = run_cli(cli_runner, ["--config", config], stdin=code)
            assert result.exit_code == 0
            assert result.stdout == expected


class TestDirectiveOrderValidation:
    rule_flags = "'-o' / '--directive-order'"
    module_flags = "'-m' / '--module-directive-order'"

    def test_unknown_rule_directive(self, cli_runner, config):
        order = f"{DEFAULT_RULE_ORDER_ARG},foo"
        result = run_cli(cli_runner, ["--config", config, "-o", order])
        problem = (
            f"unknown rule directives: 'foo' (valid rule directives are: "
            f"{RULE_VALID_NAMES})"
        )
        message = invalid_order_message(problem, RULE_DEFAULT_BLOCK)
        assert_rejected(result, self.rule_flags, message)

    def test_module_directive_in_the_rule_order(self, cli_runner, config):
        order = f"{DEFAULT_RULE_ORDER_ARG},snakefile"
        result = run_cli(cli_runner, ["--config", config, "-o", order])
        problem = (
            f"unknown rule directives: 'snakefile' (valid rule directives are: "
            f"{RULE_VALID_NAMES})"
        )
        message = invalid_order_message(problem, RULE_DEFAULT_BLOCK)
        assert_rejected(result, self.rule_flags, message)

    def test_unknown_module_directive(self, cli_runner, config):
        order = f"{DEFAULT_MODULE_ORDER_ARG},foo"
        result = run_cli(cli_runner, ["--config", config, "-m", order])
        problem = (
            f"unknown module directives: 'foo' (valid module directives are: "
            f"{MODULE_VALID_NAMES})"
        )
        message = invalid_order_message(problem, MODULE_DEFAULT_BLOCK)
        assert_rejected(result, self.module_flags, message)

    def test_rule_directive_in_the_module_order(self, cli_runner, config):
        order = f"{DEFAULT_MODULE_ORDER_ARG},input"
        result = run_cli(cli_runner, ["--config", config, "-m", order])
        problem = (
            f"unknown module directives: 'input' (valid module directives are: "
            f"{MODULE_VALID_NAMES})"
        )
        message = invalid_order_message(problem, MODULE_DEFAULT_BLOCK)
        assert_rejected(result, self.module_flags, message)

    def test_duplicate_rule_directive(self, cli_runner, config):
        order = f"{DEFAULT_RULE_ORDER_ARG},input"
        result = run_cli(cli_runner, ["--config", config, "-o", order])
        message = invalid_order_message(
            "directives listed more than once: 'input'", RULE_DEFAULT_BLOCK
        )
        assert_rejected(result, self.rule_flags, message)

    def test_duplicate_module_directive(self, cli_runner, config):
        order = f"{DEFAULT_MODULE_ORDER_ARG},name"
        result = run_cli(cli_runner, ["--config", config, "-m", order])
        message = invalid_order_message(
            "directives listed more than once: 'name'", MODULE_DEFAULT_BLOCK
        )
        assert_rejected(result, self.module_flags, message)

    @pytest.mark.parametrize("action", ACTION_DIRECTIVES)
    def test_action_directive_in_the_rule_order(self, cli_runner, config, action):
        order = f"{DEFAULT_RULE_ORDER_ARG},{action}"
        result = run_cli(cli_runner, ["--config", config, "-o", order])
        assert_rejected(result, self.rule_flags, action_directive_message(action))

    def test_action_directive_in_the_module_order_is_unknown(self, cli_runner, config):
        order = f"{DEFAULT_MODULE_ORDER_ARG},shell"
        result = run_cli(cli_runner, ["--config", config, "-m", order])
        problem = (
            f"unknown module directives: 'shell' (valid module directives are: "
            f"{MODULE_VALID_NAMES})"
        )
        message = invalid_order_message(problem, MODULE_DEFAULT_BLOCK)
        assert_rejected(result, self.module_flags, message)

    def test_several_problems_in_the_rule_order_are_reported_together(
        self, cli_runner, config
    ):
        order = "params,input,params,shell,foo"
        result = run_cli(cli_runner, ["--config", config, "-o", order])
        assert_rejected(result, self.rule_flags, SEVERAL_PROBLEMS_RULE_ORDER_MESSAGE)

    def test_names_are_reported_once_in_the_order_given(self, cli_runner, config):
        order = "params,run,input,foo,params,bar,shell,input,foo,run"
        result = run_cli(cli_runner, ["--config", config, "-o", order])
        assert_rejected(result, self.rule_flags, REPEATED_NAMES_RULE_ORDER_MESSAGE)

    def test_several_problems_in_the_module_order_are_reported_together(
        self, cli_runner, config
    ):
        order = "prefix,shell,prefix,config"
        result = run_cli(cli_runner, ["--config", config, "-m", order])
        assert_rejected(
            result, self.module_flags, SEVERAL_PROBLEMS_MODULE_ORDER_MESSAGE
        )

    def test_incomplete_rule_order(self, cli_runner, config):
        result = run_cli(cli_runner, ["--config", config, "-o", "params,input"])
        assert_rejected(
            result, "'-o' / '--directive-order'", INCOMPLETE_RULE_ORDER_MESSAGE
        )

    def test_incomplete_module_order(self, cli_runner, config):
        result = run_cli(cli_runner, ["--config", config, "-m", "prefix,config"])
        assert_rejected(
            result, "'-m' / '--module-directive-order'", INCOMPLETE_MODULE_ORDER_MESSAGE
        )

    def test_incomplete_order_in_config(self, cli_runner, tmp_path):
        config = write_config(tmp_path, 'directive_order = ["params", "input"]')
        result = run_cli(cli_runner, ["--config", config])
        assert_rejected(
            result, "'-o' / '--directive-order'", INCOMPLETE_RULE_ORDER_MESSAGE
        )

    def test_invalid_config_order_is_rejected_before_formatting(
        self, cli_runner, tmp_path
    ):
        order = toml_array((*DEFAULT_MODULE_ORDER, "input"))
        config = write_config(tmp_path, f"module_directive_order = {order}")
        snakefile = tmp_path / "Snakefile"
        snakefile.write_text(RULE_CODE)
        result = cli_runner.invoke(main, ["--config", config, str(snakefile)])
        problem = (
            f"unknown module directives: 'input' (valid module directives are: "
            f"{MODULE_VALID_NAMES})"
        )
        message = invalid_order_message(problem, MODULE_DEFAULT_BLOCK)
        assert_rejected(result, self.module_flags, message)
        assert snakefile.read_text() == RULE_CODE

    def test_non_string_config_entries_are_rejected(self, cli_runner, tmp_path):
        config = write_config(tmp_path, 'directive_order = ["input", 1]')
        result = run_cli(cli_runner, ["--config", config])
        assert_rejected(
            result,
            "'-o' / '--directive-order'",
            "the directive order must be a comma-separated string or an array of "
            "strings, not ['input', 1]",
        )


class TestNoSortWithDirectiveOrder:
    warning = (
        "A directive order was given but sorting is disabled (--no-sort), "
        "so the directive order is ignored."
    )

    def test_rule_order_is_ignored_with_a_warning(self, cli_runner, tmp_path, caplog):
        order = CUSTOM_RULE_ORDER_ARG
        args = ["--config", write_config(tmp_path), "--no-sort", "-o", order]
        result = run_cli(cli_runner, args)
        assert result.exit_code == 0
        assert result.stdout == RULE_UNSORTED
        assert warning_messages(caplog) == [self.warning]

    def test_module_order_is_ignored_with_a_warning(self, cli_runner, tmp_path, caplog):
        order = CUSTOM_MODULE_ORDER_ARG
        args = ["--config", write_config(tmp_path), "-S", "-m", order]
        result = run_cli(cli_runner, args, stdin=MODULE_CODE)
        assert result.exit_code == 0
        assert result.stdout == MODULE_UNSORTED
        assert warning_messages(caplog) == [self.warning]

    def test_config_orders_are_ignored_with_one_warning(
        self, cli_runner, tmp_path, caplog
    ):
        config = write_config(
            tmp_path,
            "sort_directives = false\n"
            f"directive_order = {toml_array(CUSTOM_RULE_ORDER)}\n"
            f"module_directive_order = {toml_array(CUSTOM_MODULE_ORDER)}",
        )
        result = run_cli(cli_runner, ["--config", config])
        assert result.exit_code == 0
        assert result.stdout == RULE_UNSORTED
        assert warning_messages(caplog) == [self.warning]

    def test_no_warning_without_a_directive_order(self, cli_runner, tmp_path, caplog):
        config = write_config(tmp_path)
        result = run_cli(cli_runner, ["--config", config, "--no-sort"])
        assert result.exit_code == 0
        assert warning_messages(caplog) == []

    def test_no_warning_when_sorting(self, cli_runner, tmp_path, caplog):
        order = CUSTOM_RULE_ORDER_ARG
        result = run_cli(cli_runner, ["--config", write_config(tmp_path), "-o", order])
        assert result.exit_code == 0
        assert warning_messages(caplog) == []


class TestPrintDirectiveOrder:
    @pytest.mark.parametrize("flag", ["-p", "--print-directive-order"])
    def test_prints_the_default_orders_in_both_forms(self, cli_runner, config, flag):
        result = cli_runner.invoke(main, ["--config", config, flag])
        assert result.exit_code == 0
        assert result.stdout == DEFAULT_PRINT

    def test_printed_toml_parses_as_is(self, cli_runner, config):
        result = cli_runner.invoke(main, ["--config", config, "-p"])
        toml_block = result.stdout.split("\n\n")[0]
        assert tomllib.loads(toml_block) == {
            "directive_order": list(DEFAULT_RULE_ORDER),
            "module_directive_order": list(DEFAULT_MODULE_ORDER),
        }

    def test_prints_a_custom_rule_order(self, cli_runner, config):
        args = ["--config", config, "-p", "-o", CUSTOM_RULE_ORDER_ARG]
        result = cli_runner.invoke(main, args)
        assert result.exit_code == 0
        assert result.stdout == CUSTOM_RULE_PRINT

    def test_prints_a_custom_module_order(self, cli_runner, config):
        args = ["--config", config, "-p", "-m", CUSTOM_MODULE_ORDER_ARG]
        result = cli_runner.invoke(main, args)
        assert result.exit_code == 0
        assert result.stdout == CUSTOM_MODULE_PRINT

    def test_prints_custom_orders_from_config(self, cli_runner, tmp_path):
        config = write_config(
            tmp_path,
            f"directive_order = {toml_array(CUSTOM_RULE_ORDER)}\n"
            f"module_directive_order = {toml_array(CUSTOM_MODULE_ORDER)}",
        )
        result = cli_runner.invoke(main, ["--config", config, "-p"])
        assert result.exit_code == 0
        assert result.stdout == CUSTOM_BOTH_PRINT

    def test_does_not_format_anything(self, cli_runner, config, tmp_path):
        snakefile = tmp_path / "Snakefile"
        snakefile.write_text(RULE_CODE)
        result = cli_runner.invoke(main, ["--config", config, "-p", str(snakefile)])
        assert result.exit_code == 0
        assert result.stdout == DEFAULT_PRINT
        assert snakefile.read_text() == RULE_CODE

    def test_rejects_an_invalid_order(self, cli_runner, config):
        order = f"{DEFAULT_RULE_ORDER_ARG},shell"
        result = cli_runner.invoke(main, ["--config", config, "-p", "-o", order])
        assert_rejected(
            result, "'-o' / '--directive-order'", action_directive_message("shell")
        )

    def test_rejects_an_incomplete_order(self, cli_runner, config):
        args = ["--config", config, "-p", "-m", "prefix,config"]
        result = cli_runner.invoke(main, args)
        assert_rejected(
            result, "'-m' / '--module-directive-order'", INCOMPLETE_MODULE_ORDER_MESSAGE
        )


class TestPrintDirectiveOrderWithNoSort:
    warning = (
        "Sorting is disabled (--no-sort), so the printed directive order "
        "is not applied."
    )

    def test_cli_no_sort_prints_the_orders_with_a_warning(
        self, cli_runner, tmp_path, caplog
    ):
        order = CUSTOM_RULE_ORDER_ARG
        args = ["--config", write_config(tmp_path), "--no-sort", "-p", "-o", order]
        result = cli_runner.invoke(main, args)
        assert result.exit_code == 0
        assert result.stdout == CUSTOM_RULE_PRINT
        assert warning_messages(caplog) == [self.warning]

    def test_config_no_sort_prints_the_orders_with_a_warning(
        self, cli_runner, tmp_path, caplog
    ):
        config = write_config(tmp_path, "sort_directives = false")
        result = cli_runner.invoke(main, ["--config", config, "-p"])
        assert result.exit_code == 0
        assert result.stdout == DEFAULT_PRINT
        assert warning_messages(caplog) == [self.warning]

    def test_no_warning_when_sorting(self, cli_runner, tmp_path, caplog):
        result = cli_runner.invoke(main, ["--config", write_config(tmp_path), "-p"])
        assert result.exit_code == 0
        assert warning_messages(caplog) == []


class TestPrintDirectiveOrderRoundTrip:
    """Using the printed orders must sort exactly as the orders that were printed."""

    cases = [
        pytest.param(
            (),
            DEFAULT_PRINT,
            (RULE_DEFAULT_ORDER, USE_RULE_DEFAULT_ORDER, MODULE_DEFAULT_ORDER),
            id="default",
        ),
        pytest.param(
            ("-o", CUSTOM_RULE_ORDER_ARG, "-m", CUSTOM_MODULE_ORDER_ARG),
            CUSTOM_BOTH_PRINT,
            (RULE_CUSTOM_ORDER, USE_RULE_CUSTOM_ORDER, MODULE_CUSTOM_ORDER),
            id="custom",
        ),
    ]
    codes = (RULE_CODE, USE_RULE_CODE, MODULE_CODE)

    def print_orders(self, cli_runner, tmp_path, args) -> str:
        result = cli_runner.invoke(
            main, ["--config", write_config(tmp_path), "-p", *args]
        )
        assert result.exit_code == 0
        return result.stdout

    @pytest.mark.parametrize("args, printed, expected", cases)
    def test_printed_toml_as_config(
        self, cli_runner, tmp_path, args, printed, expected
    ):
        output = self.print_orders(cli_runner, tmp_path, args)
        assert output == printed
        toml_block = output.split("\n\n")[0]
        config = tmp_path / "printed.toml"
        config.write_text(f"[tool.snakefmt]\n{toml_block}\n")
        for code, expected_output in zip(self.codes, expected):
            result = run_cli(cli_runner, ["--config", str(config)], stdin=code)
            assert result.exit_code == 0
            assert result.stdout == expected_output

    @pytest.mark.parametrize("args, printed, expected", cases)
    def test_printed_command_line_as_options(
        self, cli_runner, tmp_path, args, printed, expected
    ):
        output = self.print_orders(cli_runner, tmp_path, args)
        assert output == printed
        printed_options = shlex.split(output.split("# command line:\n")[1])
        config = write_config(tmp_path)
        for code, expected_output in zip(self.codes, expected):
            result = run_cli(cli_runner, ["--config", config, *printed_options], code)
            assert result.exit_code == 0
            assert result.stdout == expected_output

    def test_printed_options_print_the_same_orders(self, cli_runner, tmp_path):
        output = self.print_orders(cli_runner, tmp_path, ("-o", CUSTOM_RULE_ORDER_ARG))
        assert output == CUSTOM_RULE_PRINT
        printed_options = shlex.split(output.split("# command line:\n")[1])
        reprinted = self.print_orders(cli_runner, tmp_path, printed_options)
        assert reprinted == CUSTOM_RULE_PRINT


class TestBlockOrder:
    def test_action_directives_are_the_rule_exec_directives(self):
        assert GRAMMAR_ACTIONS == frozenset(ACTION_DIRECTIVES)

    def test_default_orders(self):
        assert RULE_ORDER.default == DEFAULT_RULE_ORDER
        assert MODULE_ORDER.default == DEFAULT_MODULE_ORDER

    def test_default_ordering_has_the_actions_last_for_rules(self):
        assert list(Rule.subautomata) == [*DEFAULT_RULE_ORDER, *ACTION_DIRECTIVES]
        assert list(UseRule.subautomata) == list(DEFAULT_RULE_ORDER)
        assert list(Module.subautomata) == list(DEFAULT_MODULE_ORDER)

    def test_complete_order_keeps_the_actions_last(self):
        assert [*RULE_ORDER.complete(CUSTOM_RULE_ORDER), *ACTION_DIRECTIVES] == [
            *CUSTOM_RULE_ORDER,
            *ACTION_DIRECTIVES,
        ]
        assert RULE_ORDER.complete(CUSTOM_RULE_ORDER) == list(CUSTOM_RULE_ORDER)
        assert MODULE_ORDER.complete(CUSTOM_MODULE_ORDER) == list(CUSTOM_MODULE_ORDER)


class TestReadmeMatchesBlocken:
    """The directive order documented in the README must be blocken's.

    blocken is authoritative, so it is the expected value here; that blocken has the
    order the tests expect is checked in `TestBlockOrder`."""

    @pytest.fixture(scope="class")
    def readme(self) -> str:
        return (Path(__file__).parent.parent / "README.md").read_text()

    @pytest.fixture(scope="class")
    def details(self, readme) -> str:
        section = readme.split("<summary>Directive ordering details</summary>")[1]
        return section.split("</details>")[0]

    def test_rule_directive_order(self, details):
        numbered_groups = [
            line for line in details.splitlines() if re.match(r"\d+\.\s", line)
        ]
        documented = [
            name for line in numbered_groups for name in re.findall(r"`(\w+)`", line)
        ]
        assert documented == list(Rule.subautomata)

    def test_module_directive_order(self, details):
        (line,) = [
            line
            for line in details.splitlines()
            if line.startswith("Modules sort their directives")
        ]
        assert re.findall(r"`(\w+)`", line) == list(Module.subautomata)

    def test_printed_orders_example(self, readme):
        command = "$ snakefmt --print-directive-order\n"
        example = readme.split(command)[1].split("```")[0]
        assert example == DEFAULT_PRINT
