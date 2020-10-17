from pathlib import Path
from unittest import mock

import black
import click
import pytest

from snakefmt import DEFAULT_LINE_LENGTH
from snakefmt.exceptions import MalformattedToml
from snakefmt.formatter import TAB
from snakefmt.snakefmt import inject_snakefmt_config, main, read_snakefmt_config
from tests import setup_formatter


def test_black_and_snakefmt_default_line_lengths_aligned():
    assert DEFAULT_LINE_LENGTH == black.DEFAULT_LINE_LENGTH


class TestConfigAdherence:
    def test_no_config_path_empty_config_dict(self):
        parsed_config = read_snakefmt_config(None)
        assert parsed_config == dict()

    def test_config_adherence_for_python_outside_rules(self, cli_runner, tmp_path):
        stdin = "include: 'a'\nlist_of_lots_of_things = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]"
        config = tmp_path / "pyproject.toml"
        config.write_text("[tool.snakefmt]\nline_length = 30\n")
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
            f"{TAB*2}list_of_lots_of_things=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],\n"
        )
        for line_length, expect_same in zip((200, 30), (True, False)):
            config = tmp_path / "pyproject.toml"
            with config.open("w") as fout:
                fout.write(f"[tool.snakefmt]\nline_length = {line_length}\n")
            params = ["--config", str(config), "-"]

            actual = cli_runner.invoke(main, params, input=stdin)

            assert actual.exit_code == 0
            if expect_same:
                assert actual.output == stdin
            else:
                assert actual.output != stdin


class TestReadSnakefmtDefaultsFromPyprojectToml:
    def test_no_value_passed_and_no_pyproject_changes_nothing(self, testdir):
        ctx = click.Context(click.Command("snakefmt"), default_map=dict())
        param = mock.MagicMock()

        return_val = inject_snakefmt_config(ctx, param, config_file=None)
        assert return_val is None
        assert ctx.default_map == dict()

    def test_empty_pyproject_is_detected_and_injects_nothing(self, testdir):
        pyproject = Path("pyproject.toml")
        pyproject.touch()
        ctx = click.Context(click.Command("snakefmt"), default_map=dict())
        param = mock.MagicMock()

        actual_config_path = inject_snakefmt_config(ctx, param, None)

        assert actual_config_path == str(pyproject)
        assert ctx.default_map == dict()

    def test_nonempty_pyproject_is_detected_and_parsed(self, testdir):
        pyproject = Path("pyproject.toml")
        pyproject.write_text("[tool.snakefmt]\nline_length = 4\n" "foo = true")
        default_map = dict(line_length=88)
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()

        parsed_config_file = inject_snakefmt_config(ctx, param, config_file=None)
        assert parsed_config_file == str(pyproject)

        expected_parameters = dict(line_length=4, foo=True)
        assert ctx.default_map == expected_parameters

    def test_passed_configfile_gets_parsed(self, testdir):
        """The configfile is not names 'pyproject.toml',
        so does not get parsed without being passed at CLI"""
        pyproject = Path("snakefmt.toml")
        pyproject.write_text("[tool.snakefmt]\nfoo = true")
        param = mock.MagicMock()

        ctx = click.Context(click.Command("snakefmt"), default_map=None)
        parsed_config_file = inject_snakefmt_config(ctx, param, config_file=None)
        assert parsed_config_file is None

        parsed_config_file = inject_snakefmt_config(
            ctx, param, config_file=str(pyproject)
        )
        assert parsed_config_file == str(pyproject)
        assert ctx.default_map == dict(foo=True)

    def test_passed_configfile_overrides_pyproject(self, testdir):
        pyproject = Path("pyproject.toml")
        pyproject.write_text("[tool.snakefmt]\n\nfoo = false\nline_length = 90")
        snakefmt_config = Path("snakefmt.toml")
        snakefmt_config.write_text("[tool.snakefmt]\nfoo = true")
        ctx = click.Context(click.Command("snakefmt"), default_map=dict())
        param = mock.MagicMock()

        inject_snakefmt_config(ctx, param, config_file=None)
        expected_parameters = dict(foo=False, line_length=90)
        assert ctx.default_map == expected_parameters

        ctx.default_map = dict()
        inject_snakefmt_config(ctx, param, config_file=str(snakefmt_config))
        expected_parameters = dict(foo=True)
        assert ctx.default_map == expected_parameters

    def test_malformatted_toml_raises_error(self, testdir):
        pyproject = Path("pyproject.toml")
        pyproject.write_text("foo:bar,baz\n{dict}&&&&")
        ctx = click.Context(click.Command("snakefmt"), default_map=dict())
        param = mock.MagicMock()
        with pytest.raises(click.FileError):
            inject_snakefmt_config(ctx, param, None)


class TestReadBlackConfig:
    def test_config_doesnt_exist_raises_error(self, tmp_path):
        formatter = setup_formatter("")
        path = tmp_path / "config.toml"
        with pytest.raises(FileNotFoundError):
            formatter.read_black_config(path)

    def test_empty_config_default_line_length_used(self, tmp_path):
        formatter = setup_formatter("")
        path = tmp_path / "config.toml"
        path.touch()
        expected = black.FileMode(line_length=DEFAULT_LINE_LENGTH)
        assert formatter.black_mode == expected

    def test_read_black_config_settings(self, tmp_path):
        formatter = setup_formatter("")
        path = tmp_path / "config.toml"
        black_line_length = 9
        path.write_text(f"[tool.black]\nline_length = {black_line_length}")

        actual = formatter.read_black_config(path)
        expected = black.FileMode(line_length=black_line_length)

        assert actual == expected

    def test_snakefmt_line_length_overrides_black(self, tmp_path):
        snakefmt_line_length = 100
        black_line_length = 10
        path = tmp_path / "config.toml"
        path.write_text(f"[tool.black]\nline_length = {black_line_length}")

        # show black gets parsed
        formatter = setup_formatter("", black_config_file=str(path))

        expected = black.FileMode(line_length=black_line_length)
        assert formatter.black_mode == expected

        # Now, add overriding snakefmt line length
        formatter = setup_formatter(
            "", line_length=snakefmt_line_length, black_config_file=str(path)
        )
        expected = black.FileMode(line_length=snakefmt_line_length)
        assert formatter.black_mode == expected

    def test_invalid_black_options_in_config_ignored(self, tmp_path):
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
        line_length = 50
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\nstring-normalization = false")
        formatter = setup_formatter(
            "", line_length=line_length, black_config_file=str(path)
        )

        expected = black.FileMode(line_length=line_length, string_normalization=False)
        assert formatter.black_mode == expected
