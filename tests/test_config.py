import os
from pathlib import Path
from unittest import mock

import click
import black
import pytest

from tests import setup_formatter
from snakefmt.snakefmt import read_snakefmt_defaults_from_pyproject_toml
from snakefmt.exceptions import InvalidBlackConfiguration, MalformattedToml


class TestReadSnakefmtDefaultsFromPyprojectToml:
    def test_no_value_passed_and_no_pyproject_changes_nothing(self, tmpdir):
        os.chdir(tmpdir)
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = None

        return_val = read_snakefmt_defaults_from_pyproject_toml(ctx, param, value)

        assert return_val is None

        actual_default_map = ctx.default_map
        expected_default_map = dict()

        assert actual_default_map == expected_default_map

    def test_pyproject_present_but_empty_changes_nothing_returns_pyproject_path(
        self, tmpdir
    ):
        os.chdir(tmpdir)
        pyproject = Path("pyproject.toml")
        pyproject.touch()
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = None

        actual_config_path = read_snakefmt_defaults_from_pyproject_toml(
            ctx, param, value
        )
        expected_config_path = None

        assert actual_config_path == expected_config_path
        assert ctx.default_map == dict()

    def test_no_value_passed_and_pyproject_present_changes_default_line_length(
        self, tmpdir
    ):
        os.chdir(tmpdir)
        pyproject = Path("pyproject.toml")
        pyproject.write_text("[tool.snakefmt]\nline_length = 4")
        default_map = dict(line_length=88)
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = None

        actual_config_path = read_snakefmt_defaults_from_pyproject_toml(
            ctx, param, value
        )
        expected_config_path = str(pyproject)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(line_length=4)

        assert actual_default_map == expected_default_map

    def test_no_value_passed_and_pyproject_present_unknown_param_adds_to_default_map(
        self, tmpdir
    ):
        os.chdir(tmpdir)
        pyproject = Path("pyproject.toml")
        pyproject.write_text("[tool.snakefmt]\nfoo = true")
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = None

        actual_config_path = read_snakefmt_defaults_from_pyproject_toml(
            ctx, param, value
        )
        expected_config_path = str(pyproject)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(foo=True)

        assert actual_default_map == expected_default_map

    def test_value_passed_reads_from_path(self, tmpdir):
        os.chdir(tmpdir)
        pyproject = Path("snakefmt.toml")
        pyproject.write_text("[tool.snakefmt]\nfoo = true")
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()

        actual_config_path = read_snakefmt_defaults_from_pyproject_toml(
            ctx, param, value=str(pyproject)
        )
        expected_config_path = str(pyproject)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(foo=True)

        assert actual_default_map == expected_default_map

    def test_value_passed_but_default_map_is_None_still_updates_defaults(self, tmpdir):
        os.chdir(tmpdir)
        pyproject = Path("snakefmt.toml")
        pyproject.write_text("[tool.snakefmt]\nfoo = true")
        default_map = None
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = str(pyproject)

        actual_config_path = read_snakefmt_defaults_from_pyproject_toml(
            ctx, param, value
        )
        expected_config_path = str(pyproject)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(foo=True)

        assert actual_default_map == expected_default_map

    def test_value_passed_in_overrides_pyproject(self, tmpdir):
        os.chdir(tmpdir)
        snakefmt_config = Path("snakefmt.toml")
        snakefmt_config.write_text("[tool.snakefmt]\nfoo = true")
        pyproject = Path("pyproject.toml")
        pyproject.write_text("[tool.snakefmt]\n\nfoo = false\nline_length = 90")
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = str(snakefmt_config)

        actual_config_path = read_snakefmt_defaults_from_pyproject_toml(
            ctx, param, value
        )
        expected_config_path = str(snakefmt_config)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(foo=True)

        assert actual_default_map == expected_default_map

    def test_malformatted_toml_raises_error(self, tmpdir):
        os.chdir(tmpdir)
        pyproject = Path("pyproject.toml")
        pyproject.write_text("foo:bar,baz\n{dict}&&&&")
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = None

        with pytest.raises(click.FileError):
            read_snakefmt_defaults_from_pyproject_toml(ctx, param, value)


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

    def test_config_exists_with_invalid_black_options_raises_error(self, tmp_path):
        formatter = setup_formatter("")
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\nfoo = false")

        with pytest.raises(InvalidBlackConfiguration) as error:
            formatter.read_black_config(path)

        assert error.match("unexpected keyword argument")

    def test_malformatted_toml_raises_error(self, tmp_path):
        formatter = setup_formatter("")
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\n{key}: I am not json:\n or yaml = false")

        with pytest.raises(MalformattedToml) as error:
            formatter.read_black_config(path)

        assert error.match("invalid character")
