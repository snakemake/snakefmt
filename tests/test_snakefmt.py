import re
import tempfile
from collections import Counter
from pathlib import Path
from typing import Optional
from unittest import mock

import pytest
from black import get_gitignore

from snakefmt.diff import ExitCode
from snakefmt.formatter import TAB
from snakefmt.snakefmt import construct_regex, get_snakefiles_in_dir, main


class TestCLIBasic:
    def test_noArgsPassed_printsNothingToDo(self, cli_runner):
        params = []
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code == 0
        assert "Nothing to do" in actual.stderr

    def test_nonExistentParam_nonZeroExit(self, cli_runner):
        params = ["--fake"]
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code != 0
        assert "no such option" in actual.stderr

    def test_invalidPath_nonZeroExit(self, cli_runner):
        params = ["fake.txt"]
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code != 0
        expected_pattern = re.compile(
            r"Path [\'\"]{}[\'\"] does not exist".format(params[0])
        )
        assert expected_pattern.search(actual.stderr)

    def test_dashMixedWithFiles_nonZeroExit(self, cli_runner):
        params = ["-", str(Path().resolve())]
        actual = cli_runner.invoke(main, params)
        assert actual.exit_code != 0
        assert "Cannot mix stdin (-) with other files" in actual.stderr

    def test_stdinAsSrc_WritesToStdout(self, cli_runner):
        stdin = f"rule all:\n{TAB}input: 'c'"
        params = ["--verbose", "-"]

        actual = cli_runner.invoke(main, params, input=stdin)

        assert actual.exit_code == 0

        expected_output = f'rule all:\n{TAB}input:\n{TAB*2}"c",\n'

        assert actual.output == expected_output

    def test_src_dir_arg_files_modified_inplace(self, cli_runner):
        with tempfile.TemporaryDirectory(dir=".") as tmpdir:
            content = 'include: "a"'
            abs_tmpdir = Path(tmpdir).resolve()
            snakedir = abs_tmpdir / "workflows"
            snakedir.mkdir()
            snakefile = snakedir / "Snakefile"
            snakefile.write_text(content)
            params = ["-v", str(tmpdir)]

            cli_runner.invoke(main, params)
            expected_contents = content + "\n"
            actual_contents = snakefile.read_text()

            assert actual_contents == expected_contents

    def test_file_arg_write_back_happens(self, cli_runner, tmp_path):
        content = 'include: "a"'
        file = tmp_path / "Snakefile"
        file.write_text(content)
        params = [str(file)]
        original_stat = file.stat()

        cli_runner.invoke(main, params)
        actual_stat = file.stat()

        assert actual_stat != original_stat

        actual_content = file.read_text()
        expected_content = content + "\n"

        assert actual_content == expected_content

    def test_file_arg_file_requires_no_changes_no_write_back_happens(
        self, cli_runner, tmp_path
    ):
        content = 'include: "a"\n'
        file = tmp_path / "Snakefile"
        file.write_text(content)
        params = [str(file)]
        expected_stat = file.stat()

        cli_runner.invoke(main, params)
        actual_stat = file.stat()

        assert actual_stat == expected_stat


class TestCLICheck:
    def test_check_file_needs_no_changes_correct_exit_code(self, cli_runner):
        stdin = 'include: "a"\n'
        params = ["--check", "-"]

        actual = cli_runner.invoke(main, params, input=stdin)

        assert ExitCode(actual.exit_code) is ExitCode.NO_CHANGE

    def test_check_file_needs_changes_correct_exit_code(self, cli_runner):
        stdin = 'include:  "a"\n'
        params = ["--check", "-"]

        actual = cli_runner.invoke(main, params, input=stdin)

        assert ExitCode(actual.exit_code) is ExitCode.WOULD_CHANGE

    def test_check_file_syntax_correct_exit_code(self, cli_runner):
        stdin = "foo:  \n"
        params = ["--check", "-"]

        actual = cli_runner.invoke(main, params, input=stdin)

        assert ExitCode(actual.exit_code) is ExitCode.ERROR

    def test_check_does_not_format_file(self, cli_runner, tmp_path):
        content = "include: 'a'\nlist_of_lots_of_things = [1, 2, 3, 4, 5, 6, 7, 8]"
        snakefile = tmp_path / "Snakefile"
        snakefile.write_text(content)
        params = ["--check", str(snakefile)]

        result = cli_runner.invoke(main, params)

        assert ExitCode(result.exit_code) is ExitCode.WOULD_CHANGE

        expected_contents = content
        actual_contents = snakefile.read_text()
        assert actual_contents == expected_contents

    def test_check_two_files_both_unchanged(self, cli_runner, tmp_path):
        content = 'include: "a"\n'
        file1 = tmp_path / "Snakefile"
        file1.write_text(content)
        file2 = tmp_path / "Snakefile2"
        file2.write_text(content)
        params = ["--check", str(file1), str(file2)]

        result = cli_runner.invoke(main, params)

        assert ExitCode(result.exit_code) is ExitCode.NO_CHANGE

    def test_check_two_files_one_will_change(self, cli_runner, tmp_path):
        content = 'include: "a"\n'
        file1 = tmp_path / "Snakefile"
        file1.write_text(content)
        file2 = tmp_path / "Snakefile2"
        content += "x='foo'"
        file2.write_text(content)
        params = ["--check", str(file1), str(file2)]

        result = cli_runner.invoke(main, params)

        assert ExitCode(result.exit_code) is ExitCode.WOULD_CHANGE

    def test_check_two_files_one_has_errors(self, cli_runner, tmp_path):
        content = 'include: "a"\n'
        file1 = tmp_path / "Snakefile"
        file1.write_text(content)
        file2 = tmp_path / "Snakefile2"
        content += "if:"
        file2.write_text(content)
        params = ["--check", str(file1), str(file2)]

        result = cli_runner.invoke(main, params)

        assert ExitCode(result.exit_code) is ExitCode.ERROR

    def test_check_and_diff_runs_both_with_check_exit_code(self, cli_runner):
        stdin = "x='foo'\n"
        params = ["--check", "--diff", "-"]

        result = cli_runner.invoke(main, params, input=stdin)

        assert ExitCode(result.exit_code) is ExitCode.WOULD_CHANGE
        expected_output = "=====> Diff for stdin <=====\n\n- x='foo'\n+ x = \"foo\"\n\n"
        assert result.output == expected_output

    def test_check_and_diff_doesnt_output_diff_if_error(self, cli_runner):
        stdin = "rule:rule:\n"
        params = ["--check", "--diff", "-"]

        result = cli_runner.invoke(main, params, input=stdin)

        assert ExitCode(result.exit_code) is ExitCode.ERROR
        assert result.output == ""


class TestCLIDiff:
    def test_diff_works_as_expected(self, cli_runner):
        stdin = "include: 'a'\n"
        params = ["--diff", "-"]

        result = cli_runner.invoke(main, params, input=stdin)
        expected_exit_code = 0

        assert result.exit_code == expected_exit_code

        expected_output = (
            "=====> Diff for stdin <=====\n"
            "\n"
            "- include: 'a'\n"
            "?          ^ ^\n"
            '+ include: "a"\n'
            "?          ^ ^\n\n"
        )

        assert result.output == expected_output

    def test_compact_diff_works_as_expected(self, cli_runner):
        stdin = "include: 'a'\n"
        params = ["--compact-diff", "-"]

        result = cli_runner.invoke(main, params, input=stdin)
        expected_exit_code = 0

        assert result.exit_code == expected_exit_code

        expected_output = (
            "=====> Diff for stdin <=====\n"
            "\n"
            "--- original\n"
            "+++ new\n"
            "@@ -1 +1 @@\n"
            "-include: 'a'\n"
            '+include: "a"\n\n'
        )

        assert result.output == expected_output

    def test_compact_diff_and_diff_given_runs_compact_diff(self, cli_runner):
        stdin = "include: 'a'\n"
        params = ["--compact-diff", "--diff", "-"]

        result = cli_runner.invoke(main, params, input=stdin)
        expected_exit_code = 0

        assert result.exit_code == expected_exit_code

        expected_output = (
            "=====> Diff for stdin <=====\n"
            "\n"
            "--- original\n"
            "+++ new\n"
            "@@ -1 +1 @@\n"
            "-include: 'a'\n"
            '+include: "a"\n\n'
        )

        assert result.output == expected_output

    def test_diff_does_not_format_file(self, cli_runner, tmp_path):
        content = "include: 'a'\nlist_of_lots_of_things = [1, 2, 3, 4, 5, 6, 7, 8]"
        snakefile = tmp_path / "Snakefile"
        snakefile.write_text(content)
        params = ["--diff", str(snakefile)]

        result = cli_runner.invoke(main, params)

        expected_exit_code = 0
        assert result.exit_code == expected_exit_code

        expected_contents = content
        actual_contents = snakefile.read_text()
        assert actual_contents == expected_contents

    def test_diff_doesnt_output_diff_if_error(self, cli_runner):
        stdin = "rule:rule:\n"
        params = ["--diff", "-"]

        result = cli_runner.invoke(main, params, input=stdin)

        assert type(result.exception) == SyntaxError
        assert result.exit_code != 0
        assert result.output == ""


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

    def test_invalid_regex_raises_error(self):
        regex = r"?"

        with pytest.raises(re.error):
            construct_regex(regex)


class TestCLIInvalidRegex:
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


class TestCLIValidRegex:
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

    def find_files_to_format(
        self, include, exclude, gitignore, gitignored: Optional[str] = None
    ):
        with tempfile.TemporaryDirectory() as tmpdir:
            abs_tmpdir = Path(tmpdir).resolve()
            self.create_temp_filesystem_in(abs_tmpdir)
            if gitignored is not None:
                with (abs_tmpdir / ".gitignore").open("w") as fout:
                    fout.write(gitignored)
                gitignore = get_gitignore(abs_tmpdir)
            snakefiles = get_snakefiles_in_dir(
                path=abs_tmpdir,
                include=include,
                exclude=exclude,
                gitignore=gitignore,
            )
            snakefiles = list(map(lambda p: str(p.relative_to(abs_tmpdir)), snakefiles))
        return Counter(snakefiles)

    @mock.patch("pathspec.PathSpec")
    def test_excludeAllFiles_returnsEmpty(self, mock_gitignore: mock.MagicMock):
        mock_gitignore.match_file.return_value = False
        include = re.compile(r"\.meow$")
        exclude = re.compile(r".*")

        actual = self.find_files_to_format(include, exclude, mock_gitignore)
        expected = Counter()
        assert actual == expected

    @mock.patch("pathspec.PathSpec")
    def test_includeAllFiles_returnAll(self, mock_gitignore: mock.MagicMock):
        mock_gitignore.match_file.return_value = False
        include = re.compile(r".*")
        exclude = re.compile(r"")

        actual = self.find_files_to_format(include, exclude, mock_gitignore)
        expected = Counter(self.filesystem)
        assert actual == expected

    @mock.patch("pathspec.PathSpec")
    def test_includeOnlySnakefiles_returnsOnlySnakefiles(
        self, mock_gitignore: mock.MagicMock
    ):
        mock_gitignore.match_file.return_value = False
        include = re.compile(r"(\.smk$|^Snakefile)")
        exclude = re.compile(r"")

        actual = self.find_files_to_format(include, exclude, mock_gitignore)
        expected = Counter(
            ["Snakefile", "Snakefile-dev", "rules/map.smk", "rules/test/test.smk"]
        )

        assert actual == expected

    def test_gitignore_paths_excluded(
        self,
    ):
        include = re.compile(r"(\.smk$|^Snakefile)")
        exclude = re.compile(r"")

        ignored_gitignore = get_gitignore(Path())
        actual_gitignored = "Snakefile*"
        actual = self.find_files_to_format(
            include, exclude, ignored_gitignore, gitignored=actual_gitignored
        )
        expected = Counter(["rules/map.smk", "rules/test/test.smk"])
        assert actual == expected


class TestCliConfig:
    def test_black_skip_string_norm_is_obeyed(self, tmp_path, cli_runner):
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\nskip-string-normalization = 1")
        stdin = "x = 'foo'\n\n\nconfigfile: 'a'\n"
        params = ["--config", str(path), "--check", "-"]

        result = cli_runner.invoke(main, params, input=stdin)
        expected_exit_code = 0

        assert result.exit_code == expected_exit_code

    def test_black_string_norm_is_obeyed(self, tmp_path, cli_runner):
        path = tmp_path / "config.toml"
        path.write_text("[tool.black]\nskip-string-normalization = false")
        stdin = "x = 'foo'\n\n\nconfigfile: 'a'\n"
        params = ["--config", str(path), "--check", "-"]

        result = cli_runner.invoke(main, params, input=stdin)

        assert result.exit_code != 0
