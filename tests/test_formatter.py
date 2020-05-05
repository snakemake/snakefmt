"""Formatting tests

The tests implicitly assume that the input syntax is correct ie that no parsing-related
errors arise, as tested in test_parser.py.
"""
from io import StringIO
from unittest import mock

import pytest

from snakefmt.formatter import TAB
from tests import setup_formatter, Snakefile, Formatter


def test_emptyInput_emptyOutput():
    formatter = setup_formatter("")

    actual = formatter.get_formatted()
    expected = ""

    assert actual == expected


class TestSimplePythonFormatting:
    @mock.patch(
        "snakefmt.formatter.Formatter.run_black_format_str", spec=True, return_value=""
    )
    def test_commented_snakemake_syntax_formatted_as_python_code(self, mock_method):
        """
        Tests this line triggers call to black formatting
        """
        formatter = setup_formatter("#configfile: 'foo.yaml'")

        formatter.get_formatted()
        mock_method.assert_called_once()

    def test_python_code_with_multi_indent_passes(self):
        python_code = "if p:\n" f"{TAB * 1}for elem in p:\n" f"{TAB * 2}dothing(elem)\n"
        # test black gets called
        with mock.patch(
            "snakefmt.formatter.Formatter.run_black_format_str",
            spec=True,
            return_value="",
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
            f'{TAB * 1}myvar = r"bytes"\n'
            f'{TAB * 1}return r"\t@RID"\n'
        )
        formatter = setup_formatter(python_code)
        assert formatter.get_formatted() == python_code

    def test_python_code_inside_run_keyword(self):
        snake_code = (
            "rule a:\n"
            f"{TAB * 1}run:\n"
            f"{TAB * 2}def s(a):\n"
            f"{TAB * 3}if a:\n"
            f'{TAB * 4}return "Hello World"\n'
        )
        formatter = setup_formatter(snake_code)
        assert formatter.get_formatted() == snake_code

    def test_line_wrapped_python_code_outside_rule(self):
        content = (
            "list_of_lots_of_things = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]\n"
            "include: snakefile"
        )
        line_length = 30
        formatter = setup_formatter(content, line_length=line_length)

        actual = formatter.get_formatted()
        expected = (
            "list_of_lots_of_things = [\n"
            f"{TAB}1,\n{TAB}2,\n{TAB}3,\n{TAB}4,\n{TAB}5,\n{TAB}6,\n{TAB}7,\n"
            f"{TAB}8,\n{TAB}9,\n{TAB}10,\n"
            "]\n"
            "\n\ninclude: snakefile\n"
        )

        assert actual == expected

    def test_line_wrapped_python_code_inside_rule(self):
        content = (
            f"rule a:\n"
            f"{TAB}input:\n"
            f"{TAB*2}list_of_lots_of_things = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]"
        )
        line_length = 30
        formatter = setup_formatter(content, line_length=line_length)

        actual = formatter.get_formatted()
        expected = (
            "rule a:\n"
            f"{TAB*1}input:\n"
            f"{TAB*2}list_of_lots_of_things=[\n"
            f"{TAB*3}1,\n{TAB*3}2,\n{TAB*3}3,\n{TAB*3}4,\n{TAB*3}5,\n"
            f"{TAB*3}6,\n{TAB*3}7,\n{TAB*3}8,\n{TAB*3}9,\n{TAB*3}10,\n"
            f"{TAB*2}],\n"
        )

        assert actual == expected


class TestComplexPythonFormatting:
    """
    Snakemake syntax can be nested inside python code
    """

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

    def test_python_code_after_nested_snakecode_gets_formatted(self):
        snakecode = "if condition:\n" f'{TAB * 1}include: "a"\n' "b=2\n"
        with mock.patch(
            "snakefmt.formatter.Formatter.run_black_format_str", spec=True
        ) as mock_m:
            mock_m.return_value = ""
            setup_formatter(snakecode)
            assert mock_m.call_count == 2
            assert mock_m.call_args_list[0] == mock.call('"a"')
            assert mock_m.call_args_list[1] == mock.call("b = 2\n")

        formatter = setup_formatter(snakecode)
        expected = (
            "if condition:\n"
            f'{TAB * 1}include: "a"\n'
            "\n\nb = 2\n"  # python code gets formatted here
        )
        assert formatter.get_formatted() == expected

    @pytest.mark.xfail(
        reason="python code prior to nested snakecode needs is not yet processed"
    )
    def test_python_code_before_nested_snakecode_gets_formatted(self):
        snakecode = "b=2\n" "if condition:\n" f'{TAB * 1}include: "a"\n'
        with mock.patch(
            "snakefmt.formatter.Formatter.run_black_format_str", spec=True
        ) as mock_m:
            formatter = setup_formatter(snakecode)
            assert mock_m.call_count == 2

        formatter = setup_formatter(snakecode)
        expected = "b = 2\n" "if condition:\n" f'{TAB * 1}include: "a"\n'
        assert formatter.get_formatted() == expected

    def test_pythoncode_parser_based_formatting_before_snakecode(self):
        snakecode = (
            'if c["a"]is None:\n'
            f'{TAB * 1}include: "a"\n'
            'elif c["b"] == "b":\n'
            f'{TAB * 1}include: "b"\n'
            'elif c["c"]=="c":\n'
            f'{TAB * 1}include: "c"\n'
        )

        formatter = setup_formatter(snakecode)
        expected = (
            'if c["a"] is None:\n'
            f'{TAB * 1}include: "a"\n'
            'elif c["b"] == "b":\n'
            f'{TAB * 1}include: "b"\n'
            'elif c["c"] == "c":\n'  # adds spaces here
            f'{TAB * 1}include: "c"\n'
        )
        assert formatter.get_formatted() == expected

    @pytest.mark.xfail(reason="black cannot format lone 'else'")
    def test_nested_snakecode_python_else_does_not_fail(self):
        snakecode = (
            'if c["a"] is None:\n'
            f'{TAB * 1}include: "a"\n'
            "else:\n"  # All python from here
            f'{TAB * 1}var = "b"\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_multiple_rules_inside_python_code(self):
        formatter = setup_formatter(
            "if condition:\n"
            f"{TAB * 1}rule a:\n"
            f'{TAB * 2}wrapper: "a"\n'
            f"{TAB * 1}rule b:\n"
            f'{TAB * 2}script: "b"'
        )
        expected = (
            "if condition:\n"
            f"{TAB * 1}rule a:\n"
            f"{TAB * 2}wrapper:\n"
            f'{TAB * 3}"a"\n'
            f"{TAB * 1}rule b:\n"
            f"{TAB * 2}script:\n"
            f'{TAB * 3}"b"\n'
        )
        assert formatter.get_formatted() == expected

    def test_parameter_keywords_inside_python_code(self):
        snakecode = (
            "if condition:\n"
            f'{TAB * 1}include: "a"\n'
            f"else:\n"
            f'{TAB * 1}include: "b"\n'
            f'\n\ninclude: "c"\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode


class TestStringFormatting:
    """Naming: tpq = triple quoted string"""

    def test_param_with_string_mixture_reindented_and_string_normalised(self):
        snakecode = (
            "rule a:\n"
            f"{TAB * 1}message:\n"
            f'{TAB * 2}"Hello"\n'
            f"{TAB * 2}'''    a string'''\n"
            f'{TAB * 3}"World"\n'
            f'{TAB * 3}"""    Yes"""\n'
        )
        expected = (
            "rule a:\n"
            f"{TAB * 1}message:\n"
            f'{TAB * 2}"Hello"\n'
            f'{TAB * 2}"""    a string"""\n'  # Quotes normalised
            f'{TAB * 2}"World"\n'
            f'{TAB * 2}"""    Yes"""\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == expected

    def test_shell_tpq_does_not_get_over_indented(self):
        snakecode = f'''
rule a:
{TAB * 1}shell:
{TAB * 2}"""
{TAB * 2}for i in $(seq 1 5)
{TAB * 2}do echo $i
{TAB * 2}done"""
'''
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_tabbed_tpq_gets_retabbed(self):
        snakecode = f'''
rule a:
{TAB * 1}shell:
{TAB * 2}"""
\t\tHello
\t\t\t\tWorld
{TAB * 2}"""
'''
        formatter = setup_formatter(snakecode)
        expected = f'''
rule a:
{TAB * 1}shell:
{TAB * 2}"""
{TAB * 2}Hello
{TAB * 4}World
{TAB * 2}"""
'''
        assert formatter.get_formatted() == expected

    def test_improperly_spaced_tpq_gets_respaced(self):
        """The "\\n" is produced when a "\n" is used in the snakefile."""
        snakecode = f'''
rule a:
  shell:
    """
    Hello"\\n"
      World
    """
'''
        formatter = setup_formatter(snakecode)

        expected = f'''
rule a:
{TAB * 1}shell:
{TAB * 2}"""
{TAB * 2}Hello"\\n"
{TAB * 2}  World
{TAB * 2}"""
'''
        assert formatter.get_formatted() == expected

    def test_docstrings_get_retabbed(self):
        """But not reindented"""
        snakecode = f'''def f():
  """Does not do
  much
    """
  pass


rule a:
  """
{' ' * 2}The rule
{' ' * 8}a
"""
  message:
    "a"
'''
        formatter = setup_formatter(snakecode)
        expected = f'''def f():
{TAB * 1}"""Does not do
  much
{TAB * 1}"""
{TAB * 1}pass


rule a:
{TAB * 1}"""
{TAB * 1}{' ' * 2}The rule
{TAB * 1}{' ' * 8}a
{TAB * 1}"""
{TAB * 1}message:
{TAB * 2}"a"
'''
        assert formatter.get_formatted() == expected


class TestSimpleParamFormatting:
    def test_simple_rule_one_input(self):
        stream = StringIO("rule a:\n" f'{TAB * 1}input: "foo.txt"')
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = "rule a:\n" f"{TAB * 1}input:\n" f'{TAB * 2}"foo.txt",\n'

        assert actual == expected

    def test_singleParamKeyword_staysOnSameLine(self):
        """
        Keywords that expect a single parameter do not have newline + indent
        """
        formatter = setup_formatter("configfile: \n" f'{TAB * 1}"foo.yaml"')

        actual = formatter.get_formatted()
        expected = 'configfile: "foo.yaml"\n'

        assert actual == expected

    def test_shell_param_newlineIndented(self):
        formatter = setup_formatter(
            "rule a:\n"
            f'{TAB * 1}shell: "for i in $(seq 1 5);"\n'
            f'{TAB * 2}"do echo $i;"\n'
            f'{TAB * 2}"done"'
        )
        expected = (
            "rule a:\n"
            f"{TAB * 1}shell:\n"
            f'{TAB * 2}"for i in $(seq 1 5);"\n'
            f'{TAB * 2}"do echo $i;"\n'
            f'{TAB * 2}"done"\n'
        )
        assert formatter.get_formatted() == expected

    def test_singleParamKeywordInRule_NewlineIndented(self):
        formatter = setup_formatter(
            f"rule a: \n"
            f'{TAB * 1}input: "a", "b",\n'
            f'{TAB * 4}"c"\n'
            f'{TAB * 1}wrapper: "mywrapper"'
        )

        actual = formatter.get_formatted()
        expected = (
            "rule a:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}"a",\n'
            f'{TAB * 2}"b",\n'
            f'{TAB * 2}"c",\n'
            f"{TAB * 1}wrapper:\n"
            f'{TAB * 2}"mywrapper"\n'
        )

        assert actual == expected

    def test_singleNumericParamKeywordInRule_staysOnSameLine(self):
        formatter = setup_formatter(
            "rule a: \n" f'{TAB * 1}input: "c"\n' f"{TAB * 1}threads:\n" f"{TAB * 2}20"
        )

        actual = formatter.get_formatted()
        expected = (
            "rule a:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}"c",\n'
            f"{TAB * 1}threads: 20\n"
        )

        assert actual == expected


class TestComplexParamFormatting:
    """
    Parameters are delimited with ','
    When ',' is present in other contexts, must be ignored
    """

    def test_expand_as_param(self):
        stream = StringIO(
            "rule a:\n"
            f"{TAB * 1}input: \n"
            f"{TAB * 2}"
            'expand("{f}/{p}", f = [1, 2], p = ["1", "2"])\n'
            f'{TAB * 1}output:"foo.txt","bar.txt"\n'
        )

        smk = Snakefile(stream)
        formatter = Formatter(smk)
        actual = formatter.get_formatted()

        expected = (
            "rule a:\n"
            f"{TAB * 1}input:\n"
            f"{TAB * 2}"
            'expand("{f}/{p}", f=[1, 2], p=["1", "2"]),\n'
            f"{TAB * 1}output:\n"
            f'{TAB * 2}"foo.txt",\n'
            f'{TAB * 2}"bar.txt",\n'
        )

        assert actual == expected

    def test_lambda_function_with_multiple_args(self):
        stream = StringIO(
            f"rule a:\n"
            f'{TAB * 1}input: "foo.txt" \n'
            f"{TAB * 1}resources:"
            f"{TAB * 2}mem_mb = lambda wildcards, attempt: attempt * 1000"
        )
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = (
            f"rule a:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}"foo.txt",\n'
            f"{TAB * 1}resources:\n"
            f"{TAB * 2}mem_mb=lambda wildcards, attempt: attempt * 1000,\n"
        )

        assert actual == expected

    def test_lambda_function_with_input_keyword_and_nested_parentheses(self):
        """
        We need to ignore 'input:' as a recognised keyword and ',' inside brackets
        Ie, the lambda needs to be parsed as a parameter.
        """
        snakefile = (
            f"rule a:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}"foo.txt",\n'
            f"{TAB * 1}params:\n"
            f"{TAB * 2}"
            'obs=lambda w, input: ["{}={}".format(s, f) for s, f in zip(get(w), input.obs)],\n'  # noqa: E501  due to readability of test
            f"{TAB * 2}p2=2,\n"
        )
        formatter = setup_formatter(snakefile)

        actual = formatter.get_formatted()
        expected = snakefile

        assert actual == expected


class TestReformatting_SMK_BREAK:
    """
    Cases where snakemake v5.13.0 raises errors, but snakefmt reformats
    such that snakemake then runs fine
    """

    def test_key_value_parameter_repositioning(self):
        formatter = setup_formatter(
            f"rule a:\n" f"{TAB * 1}input:\n" f'{TAB * 2}a="b",\n' f'{TAB * 2}"c"\n'
        )
        expected = (
            f"rule a:\n" f"{TAB * 1}input:\n" f'{TAB * 2}"c",\n' f'{TAB * 2}a="b",\n'
        )
        assert formatter.get_formatted() == expected

    def test_rule_re_indenting(self):
        formatter = setup_formatter(
            f"{TAB * 1}rule a:\n" f"{TAB * 2}wrapper:\n" f'{TAB * 3}"a"\n'
        )
        expected = f"rule a:\n" f"{TAB * 1}wrapper:\n" f'{TAB * 2}"a"\n'
        assert formatter.get_formatted() == expected


class TestCommentTreatment:
    def test_comment_after_parameter_keyword_twonewlines(self):
        snakecode = f'include: "a"\n# A comment\n'
        formatter = setup_formatter(snakecode)
        expected = f'include: "a"\n\n\n# A comment\n'
        assert formatter.get_formatted() == expected

    def test_comments_after_parameters_kept(self):
        snakecode = (
            f"rule a:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}"myparam", # a comment\n'
            f'{TAB * 2}b="param2", # another comment\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode


class TestNewlineSpacing:
    def test_parameter_keyword_spacing_above(self):
        formatter = setup_formatter("b = 2\n" 'configfile: "config.yaml"')

        actual = formatter.get_formatted()
        expected = 'b = 2\n\n\nconfigfile: "config.yaml"\n'

        assert actual == expected

    def test_parameter_keyword_spacing_below(self):
        snakecode = 'configfile: "config.yaml"\nreport: "report.rst"\n'
        formatter = setup_formatter(snakecode)
        expected = 'configfile: "config.yaml"\n\n\nreport: "report.rst"\n'

        assert formatter.get_formatted() == expected

    def test_double_spacing_for_rules(self):
        formatter = setup_formatter(
            f"""above_rule = "2spaces"
rule a:
{TAB * 1}threads: 1



rule b:
{TAB * 1}threads: 2
below_rule = "2spaces"
"""
        )

        expected = f"""above_rule = "2spaces"


rule a:
{TAB * 1}threads: 1


rule b:
{TAB * 1}threads: 2


below_rule = "2spaces"
"""
        actual = formatter.get_formatted()

        assert actual == expected

    def test_keyword_three_newlines_below_two_after_formatting(self):
        formatter = setup_formatter(f'include: "a"\n\n\n\nconfigfile: "b"\n')
        expected = f'include: "a"\n\n\nconfigfile: "b"\n'

        assert formatter.get_formatted() == expected

    def test_python_code_mixed_with_keywords_proper_spacing(self):
        snakecode = (
            "def p():\n"
            f"{TAB * 1}pass\n"
            f"include: a\n"
            f"def p2():\n"
            f"{TAB * 1}pass\n"
            f"def p3():\n"
            f"{TAB * 1}pass\n"
        )
        formatter = setup_formatter(snakecode)

        expected = (
            "def p():\n"
            f"{TAB * 1}pass\n\n\n"
            f"include: a\n\n\n"
            f"def p2():\n"
            f"{TAB * 1}pass\n\n\n"
            f"def p3():\n"
            f"{TAB * 1}pass\n"
        )

        assert formatter.get_formatted() == expected

    def test_comment_above_does_not_trigger_spacing(self):
        snakecode = (
            f"# load config\n" f"rule all:\n" f"{TAB * 1}input:\n" f"{TAB * 2}files,\n"
        )

        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_comment_below_keyword_gets_spaced(self):
        formatter = setup_formatter(
            f"""# Rules
rule all:
{TAB * 1}input: output_files
# Comment
"""
        )

        actual = formatter.get_formatted()
        expected = f"""# Rules
rule all:
{TAB * 1}input:
{TAB * 2}output_files,


# Comment
"""
        assert actual == expected
