"""Tests for the custom directive order (issue #318):
``-o/--directive-order``, the ``directive_order`` config option and
``-p/--print-directive-order``.
"""

import json
import re
import tomllib
from pathlib import Path

import pytest

from snakefmt.directive_order import ACTION_DIRECTIVES as GRAMMAR_ACTIONS
from snakefmt.parser.grammar import SnakeModule, SnakeRule, SnakeUseRule
from snakefmt.snakefmt import main
from snakefmt.types import TAB
from tests import setup_formatter

RULE_CODE = (
    "rule a:\n"
    f'{TAB}shell: "echo"\n'
    f"{TAB}threads: 1\n"
    f'{TAB}params: p="x"\n'
    f'{TAB}output: "o"\n'
    f'{TAB}input: "i"\n'
)
RULE_PARAMS_INPUT_OUTPUT_FIRST = (
    "rule a:\n"
    f"{TAB}params:\n"
    f'{TAB * 2}p="x",\n'
    f"{TAB}input:\n"
    f'{TAB * 2}"i",\n'
    f"{TAB}output:\n"
    f'{TAB * 2}"o",\n'
    f"{TAB}threads: 1\n"
    f"{TAB}shell:\n"
    f'{TAB * 2}"echo"\n'
)
RULE_THREADS_INPUT_FIRST = (
    "rule a:\n"
    f"{TAB}threads: 1\n"
    f"{TAB}input:\n"
    f'{TAB * 2}"i",\n'
    f"{TAB}output:\n"
    f'{TAB * 2}"o",\n'
    f"{TAB}params:\n"
    f'{TAB * 2}p="x",\n'
    f"{TAB}shell:\n"
    f'{TAB * 2}"echo"\n'
)
RULE_DEFAULT_ORDER = (
    "rule a:\n"
    f"{TAB}input:\n"
    f'{TAB * 2}"i",\n'
    f"{TAB}output:\n"
    f'{TAB * 2}"o",\n'
    f"{TAB}threads: 1\n"
    f"{TAB}params:\n"
    f'{TAB * 2}p="x",\n'
    f"{TAB}shell:\n"
    f'{TAB * 2}"echo"\n'
)
ACTION_DIRECTIVES = (
    "run",
    "shell",
    "script",
    "notebook",
    "wrapper",
    "cwl",
    "template_engine",
)


def format_with_order(snakecode: str, *directive_order: str) -> str:
    formatter = setup_formatter(
        snakecode, sort_params=True, directive_order=directive_order
    )
    return formatter.get_formatted()


class TestFormatterDirectiveOrder:
    def test_listed_directives_come_first_in_the_order_given(self):
        actual = format_with_order(RULE_CODE, "params", "input", "output")
        assert actual == RULE_PARAMS_INPUT_OUTPUT_FIRST

    def test_partial_list_keeps_default_order_for_unlisted_directives(self):
        code = (
            "rule a:\n"
            f'{TAB}shell: "echo"\n'
            f"{TAB}message: 'hi'\n"
            f"{TAB}threads: 1\n"
            f'{TAB}log: "l"\n'
            f'{TAB}output: "o"\n'
            f'{TAB}input: "i"\n'
        )
        expected = (
            "rule a:\n"
            f"{TAB}message:\n"
            f'{TAB * 2}"hi"\n'
            f"{TAB}input:\n"
            f'{TAB * 2}"i",\n'
            f"{TAB}output:\n"
            f'{TAB * 2}"o",\n'
            f"{TAB}log:\n"
            f'{TAB * 2}"l",\n'
            f"{TAB}threads: 1\n"
            f"{TAB}shell:\n"
            f'{TAB * 2}"echo"\n'
        )
        assert format_with_order(code, "message") == expected

    def test_empty_order_is_the_default_order(self):
        assert format_with_order(RULE_CODE) == RULE_DEFAULT_ORDER

    def test_applies_to_checkpoint(self):
        code = RULE_CODE.replace("rule a:", "checkpoint a:")
        expected = RULE_PARAMS_INPUT_OUTPUT_FIRST.replace("rule a:", "checkpoint a:")
        assert format_with_order(code, "params", "input", "output") == expected

    def test_applies_to_use_rule_and_ignores_module_directives(self):
        code = (
            "use rule a from m as b with:\n"
            f"{TAB}threads: 2\n"
            f'{TAB}output: "o"\n'
            f'{TAB}input: "i"\n'
            f"{TAB}params: p=1\n"
        )
        expected = (
            "use rule a from m as b with:\n"
            f"{TAB}params:\n"
            f"{TAB * 2}p=1,\n"
            f"{TAB}input:\n"
            f'{TAB * 2}"i",\n'
            f"{TAB}output:\n"
            f'{TAB * 2}"o",\n'
            f"{TAB}threads: 2\n"
        )
        actual = format_with_order(code, "snakefile", "params", "input", "output")
        assert actual == expected

    def test_applies_to_module_and_ignores_rule_directives(self):
        code = (
            "module m:\n"
            f'{TAB}name: "x"\n'
            f'{TAB}snakefile: "s"\n'
            f'{TAB}prefix: "p"\n'
            f"{TAB}config: config\n"
        )
        expected = (
            "module m:\n"
            f"{TAB}prefix:\n"
            f'{TAB * 2}"p"\n'
            f"{TAB}config:\n"
            f"{TAB * 2}config\n"
            f'{TAB}name: "x"\n'
            f"{TAB}snakefile:\n"
            f'{TAB * 2}"s"\n'
        )
        actual = format_with_order(code, "input", "prefix", "config")
        assert actual == expected

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
            f"{TAB}threads: 4\n"
            f"{TAB}conda:\n"
            f'{TAB * 2}"env.yaml"\n'
            f"{TAB}resources:\n"
            f"{TAB * 2}mem_mb=100,\n"
            f"{TAB}params:\n"
            f"{TAB * 2}p=1,\n"
            f"{TAB}message:\n"
            f'{TAB * 2}"finishing"\n'
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
        assert format_with_order(code, "threads", "input", "name") == expected


def run_cli(cli_runner, args, stdin=RULE_CODE):
    return cli_runner.invoke(main, [*args, "-"], input=stdin)


def write_config(tmp_path, toml_body: str) -> str:
    config = tmp_path / "pyproject.toml"
    config.write_text(f"[tool.snakefmt]\n{toml_body}\n")
    return str(config)


class TestDirectiveOrderOption:
    @pytest.mark.parametrize("flag", ["-o", "--directive-order"])
    def test_cli_option_sets_the_order(self, cli_runner, tmp_path, flag):
        config = write_config(tmp_path, "")
        args = ["--config", config, flag, "params,input,output"]
        result = run_cli(cli_runner, args)
        assert result.exit_code == 0
        assert result.stdout == RULE_PARAMS_INPUT_OUTPUT_FIRST

    def test_config_array_sets_the_order(self, cli_runner, tmp_path):
        config = write_config(
            tmp_path, 'directive_order = ["params", "input", "output"]'
        )
        result = run_cli(cli_runner, ["--config", config])
        assert result.exit_code == 0
        assert result.stdout == RULE_PARAMS_INPUT_OUTPUT_FIRST

    def test_cli_option_takes_precedence_over_config(self, cli_runner, tmp_path):
        config = write_config(tmp_path, 'directive_order = ["output", "input"]')
        args = ["--config", config, "-o", "params,input,output"]
        result = run_cli(cli_runner, args)
        assert result.exit_code == 0
        assert result.stdout == RULE_PARAMS_INPUT_OUTPUT_FIRST

    def test_whitespace_around_names_is_ignored(self, cli_runner, tmp_path):
        config = write_config(tmp_path, "")
        args = ["--config", config, "-o", " params , input,output "]
        result = run_cli(cli_runner, args)
        assert result.exit_code == 0
        assert result.stdout == RULE_PARAMS_INPUT_OUTPUT_FIRST

    @pytest.mark.parametrize("toml_value", ["[]", '""'])
    def test_empty_order_is_the_default_order(self, cli_runner, tmp_path, toml_value):
        config = write_config(tmp_path, f"directive_order = {toml_value}")
        result = run_cli(cli_runner, ["--config", config])
        assert result.exit_code == 0
        assert result.stdout == RULE_DEFAULT_ORDER


class TestDirectiveOrderValidation:
    @pytest.fixture
    def config(self, tmp_path) -> str:
        return write_config(tmp_path, "")

    def test_unknown_directive_is_rejected_and_valid_names_listed(
        self, cli_runner, config
    ):
        result = run_cli(cli_runner, ["--config", config, "-o", "input,foo"])
        assert result.exit_code == 2
        assert "unknown directive 'foo'" in result.stderr
        assert "valid directives are: name, default_target, input, output" in (
            result.stderr.replace("\n", " ")
        )

    def test_duplicate_directive_is_rejected(self, cli_runner, config):
        result = run_cli(cli_runner, ["--config", config, "-o", "input,output,input"])
        assert result.exit_code == 2
        assert "directive 'input' is listed more than once" in result.stderr

    @pytest.mark.parametrize("action", ACTION_DIRECTIVES)
    def test_action_directive_is_rejected_with_the_reason(
        self, cli_runner, config, action
    ):
        result = run_cli(cli_runner, ["--config", config, "-o", f"input,{action}"])
        assert result.exit_code == 2
        stderr = " ".join(result.stderr.split())
        assert f"'{action}' is an action directive" in stderr
        assert (
            "Snakemake allows only one action per rule and no directive may follow "
            "it, so actions are always sorted last"
        ) in stderr

    def test_invalid_config_order_is_rejected_before_formatting(
        self, cli_runner, tmp_path
    ):
        config = write_config(tmp_path, 'directive_order = ["input", "shell"]')
        snakefile = tmp_path / "Snakefile"
        snakefile.write_text(RULE_CODE)
        result = cli_runner.invoke(main, ["--config", config, str(snakefile)])
        assert result.exit_code == 2
        assert "'shell' is an action directive" in " ".join(result.stderr.split())
        assert snakefile.read_text() == RULE_CODE

    def test_non_string_config_entries_are_rejected(self, cli_runner, tmp_path):
        config = write_config(tmp_path, 'directive_order = ["input", 1]')
        result = run_cli(cli_runner, ["--config", config])
        assert result.exit_code == 2
        assert "must be a comma-separated string or an array of strings" in (
            " ".join(result.stderr.split())
        )


class TestNoSortWithDirectiveOrder:
    warning = (
        "A directive order was given but sorting is disabled (--no-sort), "
        "so the directive order is ignored."
    )

    def warnings(self, caplog) -> list[str]:
        return [r.getMessage() for r in caplog.records if r.levelname == "WARNING"]

    def test_cli_order_is_ignored_with_a_warning(self, cli_runner, tmp_path, caplog):
        config = write_config(tmp_path, "")
        args = ["--config", config, "--no-sort", "-o", "params,input,output"]
        result = run_cli(cli_runner, args)
        assert result.exit_code == 0
        assert result.stdout == (
            "rule a:\n"
            f"{TAB}shell:\n"
            f'{TAB * 2}"echo"\n'
            f"{TAB}threads: 1\n"
            f"{TAB}params:\n"
            f'{TAB * 2}p="x",\n'
            f"{TAB}output:\n"
            f'{TAB * 2}"o",\n'
            f"{TAB}input:\n"
            f'{TAB * 2}"i",\n'
        )
        assert self.warnings(caplog) == [self.warning]

    def test_config_order_is_ignored_with_a_warning(self, cli_runner, tmp_path, caplog):
        config = write_config(
            tmp_path,
            'sort_directives = false\ndirective_order = ["params", "input"]',
        )
        result = run_cli(cli_runner, ["--config", config])
        assert result.exit_code == 0
        assert result.stdout.splitlines()[1] == f"{TAB}shell:"
        assert self.warnings(caplog) == [self.warning]

    def test_no_warning_without_a_directive_order(self, cli_runner, tmp_path, caplog):
        config = write_config(tmp_path, "")
        result = run_cli(cli_runner, ["--config", config, "--no-sort"])
        assert result.exit_code == 0
        assert self.warnings(caplog) == []

    def test_no_warning_when_sorting(self, cli_runner, tmp_path, caplog):
        config = write_config(tmp_path, "")
        result = run_cli(cli_runner, ["--config", config, "-o", "params"])
        assert result.exit_code == 0
        assert self.warnings(caplog) == []


DEFAULT_ORDER_TOML = (
    'directive_order = ["name", "default_target", "input", "output", "log", '
    '"benchmark", "pathvars", "wildcard_constraints", "cache", "priority", '
    '"retries", "group", "localrule", "handover", "shadow", "conda", "container", '
    '"singularity", "containerized", "envmodules", "threads", "resources", '
    '"params", "message", "snakefile", "config", "skip_validation", "prefix", '
    '"replace_prefix", "meta_wrapper"]\n'
)
PARAMS_INPUT_ORDER_TOML = (
    'directive_order = ["params", "input", "name", "default_target", "output", '
    '"log", "benchmark", "pathvars", "wildcard_constraints", "cache", "priority", '
    '"retries", "group", "localrule", "handover", "shadow", "conda", "container", '
    '"singularity", "containerized", "envmodules", "threads", "resources", '
    '"message", "snakefile", "config", "skip_validation", "prefix", '
    '"replace_prefix", "meta_wrapper"]\n'
)


class TestPrintDirectiveOrder:
    @pytest.fixture
    def config(self, tmp_path) -> str:
        return write_config(tmp_path, "")

    @pytest.mark.parametrize("flag", ["-p", "--print-directive-order"])
    def test_prints_the_default_order_as_one_toml_line(self, cli_runner, config, flag):
        result = cli_runner.invoke(main, ["--config", config, flag])
        assert result.exit_code == 0
        assert result.stdout == DEFAULT_ORDER_TOML

    def test_prints_the_merged_order_for_a_partial_cli_order(self, cli_runner, config):
        result = cli_runner.invoke(
            main, ["--config", config, "-p", "-o", "params,input"]
        )
        assert result.exit_code == 0
        assert result.stdout == PARAMS_INPUT_ORDER_TOML

    def test_prints_the_merged_order_for_a_partial_config_order(
        self, cli_runner, tmp_path
    ):
        config = write_config(tmp_path, 'directive_order = ["params", "input"]')
        result = cli_runner.invoke(main, ["--config", config, "-p"])
        assert result.exit_code == 0
        assert result.stdout == PARAMS_INPUT_ORDER_TOML

    def test_does_not_format_anything(self, cli_runner, config, tmp_path):
        snakefile = tmp_path / "Snakefile"
        snakefile.write_text(RULE_CODE)
        result = cli_runner.invoke(main, ["--config", config, "-p", str(snakefile)])
        assert result.exit_code == 0
        assert result.stdout == DEFAULT_ORDER_TOML
        assert snakefile.read_text() == RULE_CODE

    def test_rejects_an_invalid_order(self, cli_runner, config):
        result = cli_runner.invoke(main, ["--config", config, "-p", "-o", "shell"])
        assert result.exit_code == 2
        assert "'shell' is an action directive" in result.stderr


MODULE_CODE = (
    "module m:\n"
    f'{TAB}config: "c"\n'
    f'{TAB}pathvars: x="y"\n'
    f'{TAB}name: "n"\n'
    f'{TAB}snakefile: "s"\n'
)
MODULE_DEFAULT_ORDER = (
    "module m:\n"
    f'{TAB}name: "n"\n'
    f"{TAB}pathvars:\n"
    f'{TAB * 2}x="y",\n'
    f"{TAB}snakefile:\n"
    f'{TAB * 2}"s"\n'
    f"{TAB}config:\n"
    f'{TAB * 2}"c"\n'
)
MODULE_SNAKEFILE_NAME_FIRST = (
    "module m:\n"
    f"{TAB}snakefile:\n"
    f'{TAB * 2}"s"\n'
    f'{TAB}name: "n"\n'
    f"{TAB}pathvars:\n"
    f'{TAB * 2}x="y",\n'
    f"{TAB}config:\n"
    f'{TAB * 2}"c"\n'
)


class TestPrintDirectiveOrderRoundTrip:
    """Feeding the printed order back in must sort exactly as before."""

    def printed_order(self, cli_runner, config: str, *extra_args: str) -> list[str]:
        result = cli_runner.invoke(main, ["--config", config, "-p", *extra_args])
        assert result.exit_code == 0
        return tomllib.loads(result.stdout)["directive_order"]

    def format_with_printed_order(
        self, cli_runner, tmp_path, order: list[str], code: str
    ) -> str:
        config = write_config(tmp_path, f"directive_order = {json.dumps(order)}")
        result = run_cli(cli_runner, ["--config", config], stdin=code)
        assert result.exit_code == 0
        return result.stdout

    @pytest.mark.parametrize(
        "code, expected",
        [(RULE_CODE, RULE_DEFAULT_ORDER), (MODULE_CODE, MODULE_DEFAULT_ORDER)],
    )
    def test_default_order(self, cli_runner, tmp_path, code, expected):
        empty_config = write_config(tmp_path, "")
        order = self.printed_order(cli_runner, empty_config)
        actual = self.format_with_printed_order(cli_runner, tmp_path, order, code)
        assert actual == expected

    @pytest.mark.parametrize(
        "code, expected",
        [
            (RULE_CODE, RULE_THREADS_INPUT_FIRST),
            (MODULE_CODE, MODULE_DEFAULT_ORDER),
        ],
    )
    def test_custom_order(self, cli_runner, tmp_path, code, expected):
        empty_config = write_config(tmp_path, "")
        order = self.printed_order(cli_runner, empty_config, "-o", "threads,input")
        actual = self.format_with_printed_order(cli_runner, tmp_path, order, code)
        assert actual == expected

    def test_module_directive_listed_before_a_directive_shared_with_rules(
        self, cli_runner, tmp_path
    ):
        """
        With `snakefile,name` modules sort `snakefile` before `name`. This only
        round-trips if the printed list has `snakefile` before `name` too.
        """
        empty_config = write_config(tmp_path, "")
        order = self.printed_order(cli_runner, empty_config, "-o", "snakefile,name")
        assert order[:3] == ["snakefile", "name", "default_target"]
        actual = self.format_with_printed_order(
            cli_runner, tmp_path, order, MODULE_CODE
        )
        assert actual == MODULE_SNAKEFILE_NAME_FIRST


class TestGrammarOrder:
    def test_action_directives_are_the_ones_after_the_rule_properties(self):
        assert GRAMMAR_ACTIONS == frozenset(ACTION_DIRECTIVES)

    def test_vocabulary_ordering_ignores_unrecognised_names(self):
        assert SnakeUseRule.ordered(("snakefile", "params", "input"))[:3] == [
            "params",
            "input",
            "name",
        ]
        assert SnakeModule.ordered(("input", "prefix", "config")) == [
            "prefix",
            "config",
            "name",
            "pathvars",
            "snakefile",
            "skip_validation",
            "replace_prefix",
            "meta_wrapper",
        ]

    def test_actions_stay_after_every_other_rule_directive(self):
        order = SnakeRule.ordered(("message", "name"))
        assert order[:2] == ["message", "name"]
        assert order[-7:] == list(ACTION_DIRECTIVES)


class TestReadmeMatchesGrammar:
    """The directive order documented in the README must be the grammar's."""

    @pytest.fixture(scope="class")
    def details(self) -> str:
        readme = (Path(__file__).parent.parent / "README.md").read_text()
        section = readme.split("<summary>Directive ordering details</summary>")[1]
        return section.split("</details>")[0]

    def test_rule_directive_order(self, details):
        numbered_groups = [
            line for line in details.splitlines() if re.match(r"\d+\.\s", line)
        ]
        documented = [
            name for line in numbered_groups for name in re.findall(r"`(\w+)`", line)
        ]
        assert documented == SnakeRule.ordered()

    def test_module_directive_order(self, details):
        (line,) = [
            line
            for line in details.splitlines()
            if line.startswith("Modules sort their directives")
        ]
        assert re.findall(r"`(\w+)`", line) == SnakeModule.ordered()
