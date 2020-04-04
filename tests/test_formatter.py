"""Formatting tests

The tests implicitly assume that the input syntax is correct ie that no parsing-related
errors arise, as tested in test_parser.py.
"""
from io import StringIO

import pytest
from unittest import mock

from tests import setup_formatter, Snakefile, Formatter
from snakefmt.formatter import TAB


def test_emptyInput_emptyOutput():
    formatter = setup_formatter("")

    actual = formatter.get_formatted()
    expected = ""

    assert actual == expected


class TestPythonFormatting:
    @mock.patch("snakefmt.formatter.Formatter.run_black_format_str", spec=True)
    def test_commented_snakemake_syntax_we_dont_format_but_black_does(
        self, mock_method
    ):
        """
        Tests this line triggers call to black formatting
        """
        formatter = setup_formatter("#configfile: 'foo.yaml'")

        actual = formatter.get_formatted()
        mock_method.assert_called_once()

    def test_python_code_with_multi_indent_passes(self):
        python_code = "if p:\n" "    for elem in p:\n" "        dothing(elem)\n"
        # test black gets called
        with mock.patch(
            "snakefmt.formatter.Formatter.run_black_format_str", spec=True
        ) as mock_m:
            formatter = setup_formatter(python_code)
            mock_m.assert_called_once()

        # test black formatting output (here, is identical)
        formatter = setup_formatter(python_code)
        actual = formatter.get_formatted()
        assert actual == python_code

    def test_python_code_with_rawString(self):
        python_code = (
            "def get_read_group(wildcards):\n"
            '    myvar = r"bytes"\n'
            '    return r"\t@RID"\n'
        )
        formatter = setup_formatter(python_code)
        assert formatter.get_formatted() == python_code

    def test_python_code_inside_run_keyword(self):
        snake_code = (
            "rule a:\n"
            "    run:\n"
            "        def s(a):\n"
            "            if a:\n"
            '                return "Hello World"\n'
        )
        formatter = setup_formatter(snake_code)
        assert formatter.get_formatted() == snake_code

    def test_snakemake_code_inside_python_code(self):
        # The rules inside python code get formatted
        formatter = setup_formatter(
            "if condition:\n"
            f"{TAB * 1}rule a:\n"
            f'{TAB * 2}input: "a", "b"\n'
            "else:\n"
            f"{TAB * 1}rule b:\n"
            f'{TAB * 2}script: "c.py"'
        )
        expected = (
            "if condition:\n"
            f"{TAB * 1}rule a:\n"
            f"{TAB * 2}input:\n"
            f'{TAB * 3}"a",\n'
            f'{TAB * 3}"b",\n'
            "else:\n"
            f"{TAB * 1}rule b:\n"
            f"{TAB * 2}script:\n"
            f'{TAB * 3}"c.py"\n'
        )
        assert formatter.get_formatted() == expected


class TestSimpleParamFormatting:
    def test_singleParamKeyword_staysOnSameLine(self):
        """
        Keywords that expect a single parameter do not have newline + indent
        """
        formatter = setup_formatter("configfile: \n" '    "foo.yaml"')

        actual = formatter.get_formatted()
        expected = 'configfile: "foo.yaml"\n'

        assert actual == expected

    def test_shell_keyword_get_newlineIndented(self):
        formatter = setup_formatter(
            "rule a:\n"
            '    shell: "for i in $(seq 1 5)"\n'
            '        "do echo $i"\n'
            '        "done"'
        )
        expected = (
            "rule a:\n"
            "    shell:\n"
            '        "for i in $(seq 1 5)"\n'
            '        "do echo $i"\n'
            '        "done"\n'
        )
        assert formatter.get_formatted() == expected

    def test_singleParamKeywordInRule_NewlineIndented(self):
        formatter = setup_formatter(
            "rule a: \n"
            '    input: "a", "b",\n'
            '                  "c"\n'
            '    wrapper: "mywrapper"'
        )

        actual = formatter.get_formatted()
        expected = (
            "rule a:\n"
            "    input:\n"
            '        "a",\n'
            '        "b",\n'
            '        "c",\n'
            "    wrapper:\n"
            '        "mywrapper"\n'
        )

        assert actual == expected

    def test_singleNumericParamKeywordInRule_staysOnSameLine(self):
        formatter = setup_formatter(
            "rule a: \n" '    input: "c"\n' "    threads:\n" "        20"
        )

        actual = formatter.get_formatted()
        expected = "rule a:\n" "    input:\n" '        "c",\n' "    threads: 20\n"

        assert actual == expected

    def test_simple_rule_one_input(self):
        # Differences brought about: single quote to double quote (black),
        # input parameter indentation
        stream = StringIO("rule a:\n" "    input: 'foo.txt'")
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = "rule a:\n" "    input:\n" '        "foo.txt",\n'

        assert actual == expected

    def test_lambda_function_as_parameter(self):
        stream = StringIO(
            """rule a: 
                input: lambda wildcards: foo(wildcards)"""
        )
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = """rule a:
    input:
        lambda wildcards: foo(wildcards),\n"""

        assert actual == expected


class TestCommaParamFormatting:
    """
    Parameters are delimited with ','
    When ',' is present in other contexts, must be ignored
    """

    def test_expand_as_param(self):
        stream = StringIO(
            "rule a:\n"
            "    input: \n"
            '        expand("{f}/{p}", f = [1, 2], p = ["1", "2"])\n'
            '    output:"foo.txt","bar.txt"\n'
        )

        smk = Snakefile(stream)
        formatter = Formatter(smk)
        actual = formatter.get_formatted()

        expected = (
            "rule a:\n"
            "    input:\n"
            '        expand("{f}/{p}", f=[1, 2], p=["1", "2"]),\n'
            "    output:\n"
            '        "foo.txt",\n'
            '        "bar.txt",\n'
        )

        assert actual == expected

    def test_lambda_function_with_multiple_input_params(self):
        stream = StringIO(
            "rule a:\n"
            "    input: 'foo.txt' \n"
            "    resources:"
            "        mem_mb = lambda wildcards, attempt: attempt * 1000"
        )
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = (
            "rule a:\n"
            "    input:\n"
            '        "foo.txt",\n'
            "    resources:\n"
            "        mem_mb=lambda wildcards, attempt: attempt * 1000,\n"
        )

        assert actual == expected

    def test_lambda_function_with_input_keyword_and_nested_parentheses(self):
        """
        We need to ignore 'input:' as a recognised keyword and ',' inside brackets
        Ie, the lambda needs to be parsed as a parameter.
        """
        snakefile = (
            "rule a:\n"
            "    input:\n"
            '        "foo.txt",\n'
            "    params:\n"
            '        obs=lambda w, input: ["{}={}".format(s, f) for s, f in zip(get_group_aliases(w), input.obs)],\n'
            "        p2=2,\n"
        )
        formatter = setup_formatter(snakefile)

        actual = formatter.get_formatted()
        expected = snakefile

        assert actual == expected


class TestNewlineSpacing:
    def test_non_rule_has_no_keyword_spacing_above(self):
        formatter = setup_formatter("# load config\n" 'configfile: "config.yaml"')

        actual = formatter.get_formatted()
        expected = '# load config\nconfigfile: "config.yaml"\n'

        assert actual == expected

    def test_non_rule_has_no_keyword_spacing_below(self):
        snakestring = 'configfile: "config.yaml"\nreport: "report.rst"\n'
        formatter = setup_formatter(snakestring)

        formatter.get_formatted() == snakestring

    def test_rule_needs_double_spacing_above(self):
        formatter = setup_formatter('foo = "bar"\nrule all:\n    input:\n        "a"\n')

        actual = formatter.get_formatted()
        expected = 'foo = "bar"\n\n\nrule all:\n    input:\n        "a",\n'

        assert actual == expected

    def test_rule_with_three_newlines_above_only_has_two_after_formatting(self):
        formatter = setup_formatter(
            'foo = "bar"\n\n\n\nrule all:\n    input:\n        "a"\n'
        )

        actual = formatter.get_formatted()
        expected = 'foo = "bar"\n\n\nrule all:\n    input:\n        "a",\n'

        assert actual == expected

    def test_rule_needs_double_spacing_below(self):
        formatter = setup_formatter('rule all:\n    input:\n        "a"\nfoo = "bar"\n')

        actual = formatter.get_formatted()
        expected = 'rule all:\n    input:\n        "a",\n\n\nfoo = "bar"\n'

        assert actual == expected

    def test_rule_with_three_newlines_below_only_has_two_after_formatting(self):
        formatter = setup_formatter(
            'rule all:\n    input:\n        "a"\n\n\n\nfoo = "bar"'
        )

        actual = formatter.get_formatted()
        expected = 'rule all:\n    input:\n        "a",\n\n\nfoo = "bar"\n'

        assert actual == expected

    def test_comment_exempt_from_keyword_spacing(self):
        formatter = setup_formatter("# load config\n" "rule all:\n    input:files")

        actual = formatter.get_formatted()
        expected = "# load config\nrule all:\n    input:\n        files,\n"

        assert actual == expected

    def test_comment_below_rule_is_not_ignored_from_spacing(self):
        formatter = setup_formatter(
            """# ======================================================
# Rules
# ======================================================
rule all:
    input: output_files

# https://github.com/nanoporetech/taiyaki/blob/master/docs/walkthrough.rst#bam-of-mapped-basecalls"""
        )

        actual = formatter.get_formatted()
        expected = """# ======================================================
# Rules
# ======================================================
rule all:
    input: 
        output_files,


# https://github.com/nanoporetech/taiyaki/blob/master/docs/walkthrough.rst#bam-of-mapped-basecalls"""
