from pathlib import Path
from unittest import mock

import black
import click
import pytest

from snakefmt.exceptions import MalformattedToml
from snakefmt.formatter import TAB
from snakefmt.snakefmt import inject_snakefmt_config, main
from tests import setup_formatter


class TestConfigAdherence:
    def test_config_adherence_for_python_outside_rules(self, cli_runner, tmp_path):
        stdin = "include: 'a'\nlist_of_lots_of_things = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]"
        line_length = 30
        config = tmp_path / "pyproject.toml"
        config.write_text(f"[tool.snakefmt]\nline_length = {line_length}\n")
        params = ["--config", str(config), "-"]

        actual = cli_runner.invoke(main, params, input=stdin)
        assert actual.exit_code == 0

        expected_output = """include: \"a\"


list_of_lots_of_things = [
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    8,
    9,
    10,
]
"""
        assert actual.output == expected_output

    def test_config_adherence_for_code_inside_rules(self, cli_runner, tmp_path):
        stdin = (
            f"rule a:\n"
            f"{TAB}input:\n"
            f"{TAB*2}list_of_lots_of_things = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]"
        )
        line_length = 30
        config = tmp_path / "pyproject.toml"
        config.write_text(f"[tool.snakefmt]\nline_length = {line_length}\n")
        params = ["--config", str(config), "-"]

        actual = cli_runner.invoke(main, params, input=stdin)

        assert actual.exit_code == 0

        expected_output = (
            "rule a:\n"
            f"{TAB*1}input:\n"
            f"{TAB*2}list_of_lots_of_things=[\n"
            f"{TAB*3}1,\n{TAB*3}2,\n{TAB*3}3,\n{TAB*3}4,\n{TAB*3}5,\n"
            f"{TAB*3}6,\n{TAB*3}7,\n{TAB*3}8,\n{TAB*3}9,\n{TAB*3}10,\n"
            f"{TAB*2}],\n"
        )

        assert actual.output == expected_output


class TestReadSnakefmtDefaultsFromPyprojectToml:
    def test_no_value_passed_and_no_pyproject_changes_nothing(self, testdir):
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = None

        return_val = inject_snakefmt_config(ctx, param, value)

        assert return_val is None

        actual_default_map = ctx.default_map
        expected_default_map = dict()

        assert actual_default_map == expected_default_map

    def test_pyproject_present_but_empty_changes_nothing_returns_pyproject_path(
        self, testdir
    ):
        pyproject = Path("pyproject.toml")
        pyproject.touch()
        ctx = click.Context(click.Command("snakefmt"), default_map=dict())
        param = mock.MagicMock()

        actual_config_path = inject_snakefmt_config(ctx, param, None)

        assert actual_config_path == str(pyproject)
        assert ctx.default_map == dict()

    def test_no_value_passed_and_pyproject_present_changes_default_line_length(
        self, testdir
    ):
        pyproject = Path("pyproject.toml")
        pyproject.write_text("[tool.snakefmt]\nline_length = 4")
        default_map = dict(line_length=88)
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = None

        actual_config_path = inject_snakefmt_config(ctx, param, value)
        expected_config_path = str(pyproject)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(line_length=4)

        assert actual_default_map == expected_default_map

    def test_no_value_passed_and_pyproject_present_unknown_param_adds_to_default_map(
        self, testdir
    ):
        pyproject = Path("pyproject.toml")
        pyproject.write_text("[tool.snakefmt]\nfoo = true")
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = None

        actual_config_path = inject_snakefmt_config(ctx, param, value)
        expected_config_path = str(pyproject)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(foo=True)

        assert actual_default_map == expected_default_map

    def test_value_passed_reads_from_path(self, testdir):
        pyproject = Path("snakefmt.toml")
        pyproject.write_text("[tool.snakefmt]\nfoo = true")
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()

        actual_config_path = inject_snakefmt_config(
            ctx, param, config_file=str(pyproject)
        )
        expected_config_path = str(pyproject)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(foo=True)

        assert actual_default_map == expected_default_map

    def test_value_passed_but_default_map_is_None_still_updates_defaults(self, testdir):
        pyproject = Path("snakefmt.toml")
        pyproject.write_text("[tool.snakefmt]\nfoo = true")
        default_map = None
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = str(pyproject)

        actual_config_path = inject_snakefmt_config(ctx, param, value)
        expected_config_path = str(pyproject)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(foo=True)

        assert actual_default_map == expected_default_map

    def test_value_passed_in_overrides_pyproject(self, testdir):
        snakefmt_config = Path("snakefmt.toml")
        snakefmt_config.write_text("[tool.snakefmt]\nfoo = true")
        pyproject = Path("pyproject.toml")
        pyproject.write_text("[tool.snakefmt]\n\nfoo = false\nline_length = 90")
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = str(snakefmt_config)

        actual_config_path = inject_snakefmt_config(ctx, param, value)
        expected_config_path = str(snakefmt_config)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(foo=True)

        assert actual_default_map == expected_default_map

    def test_malformatted_toml_raises_error(self, testdir):
        pyproject = Path("pyproject.toml")
        pyproject.write_text("foo:bar,baz\n{dict}&&&&")
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = None

        with pytest.raises(click.FileError):
            inject_snakefmt_config(ctx, param, value)


class TestReadBlackConfig:
    def test_config_doesnt_exist_raises_error(self, tmp_path):
        formatter = setup_formatter("")
        path = tmp_path / "config.toml"
        with pytest.raises(FileNotFoundError):
            formatter.read_black_config(path)

    def test_config_exists_but_no_black_settings(self, tmp_path):
        formatter = setup_formatter("")
        path = tmp_path / "config.toml"
        path.write_text("[tool.snakefmt]\nline_length = 99")

        actual = formatter.read_black_config(path)
        expected = black.FileMode(line_length=formatter.line_length)

        assert actual == expected

    def test_config_exists_with_black_settings(self, tmp_path):
        formatter = setup_formatter("")
        path = tmp_path / "config.toml"
        black_line_length = 9
        path.write_text(f"[tool.black]\nline_length = {black_line_length}")

        actual = formatter.read_black_config(path)
        expected = black.FileMode(line_length=black_line_length)

        assert actual == expected

    def test_config_exists_with_no_line_length_uses_snakefmt_line_length(
        self, tmp_path
    ):
        line_length = 9
        formatter = setup_formatter("", line_length=line_length)
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\nstring_normalization = false")

        actual = formatter.read_black_config(path)
        expected = black.FileMode(line_length=line_length, string_normalization=False)

        assert actual == expected

    def test_config_exists_with_invalid_black_options_ignores_it(self, tmp_path):
        formatter = setup_formatter("")
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\nfoo = false")

        actual = formatter.read_black_config(path)
        expected = black.FileMode()

        assert actual == expected

    def test_malformatted_toml_raises_error(self, tmp_path):
        formatter = setup_formatter("")
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\n{key}: I am not json:\n or yaml = false")

        with pytest.raises(MalformattedToml) as error:
            formatter.read_black_config(path)

        assert error.match("invalid character")

    def test_skip_string_normalisation_handled_with_snakecase(self, tmp_path):
        line_length = 88
        formatter = setup_formatter("", line_length=line_length)
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\nskip_string_normalization = false")

        actual = formatter.read_black_config(path)
        expected = black.FileMode(line_length=line_length, string_normalization=True)

        assert actual == expected

    def test_skip_string_normalisation_handled_with_kebabcase(self, tmp_path):
        line_length = 88
        formatter = setup_formatter("", line_length=line_length)
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\nskip-string-normalization = 0")

        actual = formatter.read_black_config(path)
        expected = black.FileMode(line_length=line_length, string_normalization=True)

        assert actual == expected

    def test_string_normalisation_handled(self, tmp_path):
        line_length = 88
        formatter = setup_formatter("", line_length=line_length)
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\nstring-normalization = false")

        actual = formatter.read_black_config(path)
        expected = black.FileMode(line_length=line_length, string_normalization=False)

        assert actual == expected
