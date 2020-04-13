import re
import tempfile
from collections import Counter
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner

from snakefmt.snakefmt import (
    construct_regex,
    main,
    get_snakefiles_in_dir,
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
