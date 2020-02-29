import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from snakefmt.snakefmt import construct_regex, main, get_snakefiles_in_dir


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
        assert f'Path "{params[0]}" does not exist' in actual.output

    def test_dashMixedWithFiles_nonZeroExit(self, cli_runner):
        params = ["-", str(Path().resolve())]
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code != 0
        assert "Cannot mix stdin (-) with other files" in actual.output


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
    def test_noFiles_returnsEmpty(self):
        pass
