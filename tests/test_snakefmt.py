import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner

from snakefmt.formatter import TAB
from snakefmt.snakefmt import (
    construct_regex,
    main,
    get_snakefiles_in_dir,
    read_snakefmt_defaults_from_pyproject_toml,
)


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


class TestCLI:
    def test_noArgsPassed_printsNothingToDo(self, cli_runner):
        params = []
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code == 0
        assert "Nothing to do" in actual.output

    def test_nonExistantParam_nonZeroExit(self, cli_runner):
        params = ["--fake"]
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code != 0
        assert "no such option" in actual.output

    def test_invalidPath_nonZeroExit(self, cli_runner):
        params = ["fake.txt"]
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code != 0
        expected_pattern = re.compile(
            r"Path [\'\"]{}[\'\"] does not exist".format(params[0])
        )
        assert expected_pattern.search(actual.output)

    def test_dashMixedWithFiles_nonZeroExit(self, cli_runner):
        params = ["-", str(Path().resolve())]
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code != 0
        assert "Cannot mix stdin (-) with other files" in actual.output

    def test_invalidIncludeRegex_nonZeroExit(self, cli_runner):
        params = ["--include", "?", str(Path().resolve())]
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code != 0
        assert "Invalid regular expression" in str(actual.exception)

    def test_invalidExcludeRegex_nonZeroExit(self, cli_runner):
        params = ["--exclude", "?", str(Path().resolve())]
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code != 0
        assert "Invalid regular expression" in str(actual.exception)

    def test_stdinAsSrc_WritesToStdout(self, cli_runner):
        stdin = f"rule all:\n{TAB}input: 'c'"
        params = ["--verbose", "-"]

        actual = cli_runner.invoke(main, params, input=stdin)

        assert actual.exit_code == 0

        expected_output = f'rule all:\n{TAB}input:\n{TAB*2}"c",\n\n'

        assert actual.output == expected_output

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
        stdin = f"rule a:\n{TAB}input:\n{TAB*2}list_of_lots_of_things = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]"
        line_length = 30
        config = tmp_path / "pyproject.toml"
        config.write_text(f"[tool.snakefmt]\nline_length = {line_length}\n")
        params = ["--config", str(config), "-"]

        actual = cli_runner.invoke(main, params, input=stdin)

        assert actual.exit_code == 0

        expected_output = f"""rule a:
{TAB*1}input:
{TAB*2}list_of_lots_of_things=[
{TAB*3}1,
{TAB*3}2,
{TAB*3}3,
{TAB*3}4,
{TAB*3}5,
{TAB*3}6,
{TAB*3}7,
{TAB*3}8,
{TAB*3}9,
{TAB*3}10,
{TAB*2}],
        
"""

        assert actual.output == expected_output


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

    def test_no_value_passed_and_pyproject_present_but_empty_changes_nothing_returns_pyproject_path(
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

        actual_default_map = ctx.default_map
        expected_default_map = dict()

        assert actual_default_map == expected_default_map

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
        value = str(pyproject)

        actual_config_path = read_snakefmt_defaults_from_pyproject_toml(
            ctx, param, value
        )
        expected_config_path = str(pyproject)

        assert actual_config_path == expected_config_path

        actual_default_map = ctx.default_map
        expected_default_map = dict(foo=True)

        assert actual_default_map == expected_default_map

    def test_value_passed_but_default_map_is_empty_still_updates_defaults(self, tmpdir):
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
        pyproject.write_text("foo:bar,baz\n{dict}\&&&&")
        default_map = dict()
        ctx = click.Context(click.Command("snakefmt"), default_map=default_map)
        param = mock.MagicMock()
        value = None

        with pytest.raises(click.FileError):
            read_snakefmt_defaults_from_pyproject_toml(ctx, param, value)


class TestConstructRegex:
    def test_noNewline_returnsCompiledRegex(self):
        regex = r"\.smk$"

        actual = construct_regex(regex)
        expected = re.compile(regex)

        assert actual == expected

    def test_containsNewline_returnsCompiledRegexWithMultilineSetting(self):
        regex = r"""
(
  /(
      \.eggs         # exclude a few common directories in the
    | \.git          # root of the project
    | \.snakemake
  )/
)
"""

        actual = construct_regex(regex)
        expected = re.compile(regex, re.MULTILINE | re.VERBOSE)

        assert actual == expected

    def test_invalidRegex_raisesError(self):
        regex = r"?"

        with pytest.raises(re.error):
            construct_regex(regex)


class TestGetSnakefilesInDir:
    filesystem = [
        "Snakefile",
        "Snakefile-dev",
        "scripts/run.py",
        "rules/map.smk",
        "rules/test/test.smk",
        "data/file.txt",
        "config.yml",
        "a/b/c/d/e/Snakefil",
        "a/b/c/d/foo.bar",
    ]

    def create_temp_filesystem_in(self, tmpdir: Path):
        for p in self.filesystem:
            path = tmpdir / p
            parent = path.parent
            parent.mkdir(exist_ok=True, parents=True)
            path.touch()

    @mock.patch("pathspec.PathSpec")
    def test_excludeAllFiles_returnsEmpty(self, mock_gitignore: mock.MagicMock):
        mock_gitignore.match_file.return_value = False
        include = re.compile(r"\.meow$")
        exclude = re.compile(r".*")

        with tempfile.TemporaryDirectory() as tmpdir:
            abs_tmpdir = Path(tmpdir).resolve()
            self.create_temp_filesystem_in(abs_tmpdir)
            snakefiles = get_snakefiles_in_dir(
                path=Path(tmpdir),
                root=abs_tmpdir,
                include=include,
                exclude=exclude,
                gitignore=mock_gitignore,
            )

            actual = Counter(snakefiles)
            expected = Counter()

            assert actual == expected

    @mock.patch("pathspec.PathSpec")
    def test_includeAllFiles_returnAll(self, mock_gitignore: mock.MagicMock):
        mock_gitignore.match_file.return_value = False
        include = re.compile(r".*")
        exclude = re.compile(r"")

        with tempfile.TemporaryDirectory() as tmpdir:
            abs_tmpdir = Path(tmpdir).resolve()
            self.create_temp_filesystem_in(abs_tmpdir)
            snakefiles = get_snakefiles_in_dir(
                path=Path(tmpdir),
                root=abs_tmpdir,
                include=include,
                exclude=exclude,
                gitignore=mock_gitignore,
            )

            actual = Counter(snakefiles)
            expected = Counter(Path(tmpdir) / p for p in self.filesystem)

            assert actual == expected

    @mock.patch("pathspec.PathSpec")
    def test_includeOnlySnakefiles_returnsOnlySnakefiles(
        self, mock_gitignore: mock.MagicMock
    ):
        mock_gitignore.match_file.return_value = False
        include = re.compile(r"(\.smk$|^Snakefile)")
        exclude = re.compile(r"")

        with tempfile.TemporaryDirectory() as tmpdir:
            abs_tmpdir = Path(tmpdir).resolve()
            self.create_temp_filesystem_in(abs_tmpdir)
            snakefiles = get_snakefiles_in_dir(
                path=Path(tmpdir),
                root=abs_tmpdir,
                include=include,
                exclude=exclude,
                gitignore=mock_gitignore,
            )

            actual = Counter(snakefiles)
            expected = Counter(
                Path(tmpdir) / p
                for p in [
                    "Snakefile",
                    "Snakefile-dev",
                    "rules/map.smk",
                    "rules/test/test.smk",
                ]
            )

            assert actual == expected
