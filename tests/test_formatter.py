"""Formatting tests

The tests implicitly assume that the input syntax is correct ie that no parsing-related
errors arise, as tested in test_parser.py.
"""
from io import StringIO
from unittest import mock

import pytest

from snakefmt.parser.grammar import SingleParam, SnakeGlobal
from snakefmt.parser.syntax import COMMENT_SPACING
from snakefmt.types import TAB
from tests import Formatter, Snakefile, setup_formatter


def test_emptyInput_emptyOutput():
    formatter = setup_formatter("")

    actual = formatter.get_formatted()
    expected = ""

    assert actual == expected


class TestSimpleParamFormatting:
    def test_simple_rule_one_input(self):
        stream = StringIO("rule a:\n" f'{TAB * 1}input: "foo.txt"')
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = "rule a:\n" f"{TAB * 1}input:\n" f'{TAB * 2}"foo.txt",\n'

        assert actual == expected

    def test_single_param_keyword_stays_on_same_line(self):
        """
        Keywords that expect a single parameter do not have newline + indent
        """
        formatter = setup_formatter("configfile: \n" f'{TAB * 1}"foo.yaml"')

        actual = formatter.get_formatted()
        expected = 'configfile: "foo.yaml"\n'

        assert actual == expected

    def test_shell_param_newline_indented(self):
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

    def test_single_param_keyword_in_rule_gets_newline_indented(self):
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

    def test_single_numeric_param_keyword_in_rule_stays_on_same_line(self):
        formatter = setup_formatter(
            "rule a: \n"
            f'{TAB * 1}input: "c"\n'
            f"{TAB * 1}threads:\n"
            f"{TAB * 2}20\n"
            f"{TAB * 1}default_target:\n"
            f"{TAB * 2}True\n"
        )

        actual = formatter.get_formatted()
        expected = (
            f'rule a:\n{TAB * 1}input:\n{TAB * 2}"c",\n{TAB * 1}threads: 20\n'
            f"{TAB * 1}default_target: True\n"
        )

        assert actual == expected


class TestModuleFormatting:
    def test_module_specific_keyword_formatting(self):
        formatter = setup_formatter(
            "module a: \n"
            f'{TAB * 1}snakefile: "other.smk"\n'
            f"{TAB * 1}config: config\n"
            f'{TAB * 1}prefix: "testmodule"\n'
            f'{TAB * 1}replace_prefix: {{"results/": "results/testmodule/"}}\n'
            f'{TAB * 1}meta_wrapper: "0.72.0/meta/bio/bwa_mapping"\n'
        )

        expected = (
            "module a:\n"
            f"{TAB * 1}snakefile:\n"
            f'{TAB * 2}"other.smk"\n'
            f"{TAB * 1}config:\n"
            f"{TAB * 2}config\n"
            f"{TAB * 1}prefix:\n"
            f'{TAB * 2}"testmodule"\n'
            f"{TAB * 1}replace_prefix:\n"
            f'{TAB * 2}{{"results/": "results/testmodule/"}}\n'
            f"{TAB * 1}meta_wrapper:\n"
            f'{TAB * 2}"0.72.0/meta/bio/bwa_mapping"\n'
        )

        assert formatter.get_formatted() == expected


class TestUseRuleFormatting:
    def test_use_rule_rule_like_indented(self):
        snakecode = (
            'include: "file.txt"\n\n\n'
            "use rule a from module with:\n"
            f"{TAB * 1}input:\n"
            f"{TAB * 2}b=2,\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_use_rule_with_exclude(self):
        snakecode = """from snakemake.utils import min_version


min_version("6.0")


module other_workflow:
    snakefile:
        # here is a comment
        "other_workflow/Snakefile"


use rule * from other_workflow exclude ruleC as other_*
"""
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_use_rule_with_multiple_excludes(self):
        snakecode = """from snakemake.utils import min_version


min_version("6.0")


module other_workflow:
    snakefile:
        # here is a comment
        "other_workflow/Snakefile"


use rule * from other_workflow exclude ruleC, foo as other_*
"""
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_use_rule_no_with_two_line_indented(self):
        snakecode = 'include: "file.txt"\n\n\n' "use rule * from module as module_*\n"
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_use_rule_with_comment(self):
        snakecode = (
            "# Comment here\n\n\n"
            "use rule * from module as module_*  # Use these cool rules\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_use_rule_newline_spacing(self):
        snakecode = (
            "use rule * from module as module_*\n\n\n"
            "rule baz:\n"
            f"{TAB * 1}threads: 4\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode


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

    def test_lambda_function_with_multiple_args_and_ifelse(self):
        snakecode = (
            f"rule a:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}"foo.txt",\n'
            f"{TAB * 1}resources:\n"
            f"{TAB * 2}time_min=lambda wildcards, attempt: (\n"
            f'{TAB * 3}60 * 23 if "cv" in wildcards.method else 60 * 10\n'
            f"{TAB * 2})\n"
            f"{TAB * 2}* attempt,\n"
        )
        formatter = setup_formatter(snakecode)
        actual = formatter.get_formatted()
        assert actual == snakecode

    def test_lambda_function_with_keyword_arg(self):
        snakecode = (
            f"rule a:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}"foo.txt",\n'
            f"{TAB * 1}resources:\n"
            f"{TAB * 2}mem_mb=lambda wildcards, attempt, mem=1000: attempt * mem,\n"
        )
        formatter = setup_formatter(snakecode)
        actual = formatter.get_formatted()
        assert actual == snakecode

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

    def test_arg_and_kwarg_unpacking(self):
        """issue 109"""
        snakecode = (
            f"rule r:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}*["a", "b", "c"],\n'
            f"{TAB * 2}*myfunc(a=1),\n"
            f'{TAB * 2}**{{"a": "b", "c": "d"}},\n'
            f"{TAB * 2}**myfunc(a=1, b=2),\n"
            f"{TAB * 2}**module.myfunc(a=1, b=2),\n"
        )
        formatter = setup_formatter(snakecode)
        actual = formatter.get_formatted()
        assert actual == snakecode


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
            setup_formatter(python_code)
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
        content = "list_of_lots_of_things = [1, 2, 3, 4, 5, 6]\n" "include: snakefile"
        line_length = 30
        formatter = setup_formatter(content, line_length=line_length)

        actual = formatter.get_formatted()
        expected = (
            "list_of_lots_of_things = [\n"
            f"{TAB}1,\n{TAB}2,\n{TAB}3,\n{TAB}4,\n{TAB}5,\n{TAB}6,\n"
            "]\n"
            "\n\ninclude: snakefile\n"
        )

        assert actual == expected

    def test_line_wrapped_python_code_inside_rule(self):
        content = (
            f"rule a:\n"
            f"{TAB}input:\n"
            f"{TAB*2}list_of_lots_of_things = [1, 2, 3, 4, 5]"
        )
        line_length = 30
        formatter = setup_formatter(content, line_length=line_length)

        actual = formatter.get_formatted()
        expected = (
            "rule a:\n"
            f"{TAB*1}input:\n"
            f"{TAB*2}list_of_lots_of_things=[\n"
            f"{TAB*3}1,\n{TAB*3}2,\n{TAB*3}3,\n{TAB*3}4,\n{TAB*3}5,\n"
            f"{TAB*2}],\n"
        )

        assert actual == expected


class TestComplexPythonFormatting:
    """
    Snakemake syntax can be nested inside python code

    As for black non-top level functions, 1 line spacing is used between
    code and keywords, and two between keyword and code.
    """

    def test_if_statement_with_snakecode_2comments_snakecode_inside(self):
        """https://github.com/snakemake/snakefmt/issues/159"""
        snakecode = (
            "if True:\n\n"
            f"{TAB * 1}ruleorder: a > b\n"
            f"{TAB * 1}# comment\n"
            f"{TAB * 1}# comment\n"
            f"{TAB * 1}ruleorder: c > d\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_snakemake_code_inside_python_code(self):
        formatter = setup_formatter(
            "if condition:\n"
            f"{TAB * 1}rule a:\n"
            f'{TAB * 2}input: "a", "b"\n'
            "else:\n"
            f"{TAB * 1}rule b:\n"
            f'{TAB * 2}script: "c.py"'
        )
        expected = (
            "if condition:\n\n"
            f"{TAB * 1}rule a:\n"
            f"{TAB * 2}input:\n"
            f'{TAB * 3}"a",\n'
            f'{TAB * 3}"b",\n\n'
            "else:\n\n"
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
            mock_m.return_value = "if condition:\n"
            setup_formatter(snakecode)
            assert mock_m.call_count == 3
            assert mock_m.call_args_list[1] == mock.call('"a"', 0, 0, no_nesting=True)
            assert mock_m.call_args_list[2] == mock.call("b = 2\n", 0)

        formatter = setup_formatter(snakecode)
        expected = (
            "if condition:\n\n"
            f'{TAB * 1}include: "a"\n'
            "\n\nb = 2\n"  # python code gets formatted here
        )
        assert formatter.get_formatted() == expected

    def test_python_code_before_nested_snakecode_gets_formatted(self):
        snakecode = "b=2\n" "if condition:\n" f'{TAB * 1}include: "a"\n'
        with mock.patch(
            "snakefmt.formatter.Formatter.run_black_format_str", spec=True
        ) as mock_m:
            mock_m.return_value = "b=2\nif condition:\n"
            setup_formatter(snakecode)
            assert mock_m.call_count == 2

        formatter = setup_formatter(snakecode)
        expected = "b = 2\n" "if condition:\n\n" f'{TAB * 1}include: "a"\n'
        assert formatter.get_formatted() == expected

    def test_pythoncode_parser_based_formatting_before_snakecode(self):
        snakecode = (
            'if c["a"]is None:\n\n'  # space needed before '['
            f'{TAB * 1}include: "a"\n\n\n'
            'elif myobj.attr == "b":\n\n'
            f'{TAB * 1}include: "b"\n\n\n'
            'elif len(c["c"])==3:\n\n'  # spaces needed either side of '=='
            f'{TAB * 1}include: "c"\n'
        )

        formatter = setup_formatter(snakecode)
        expected = (
            'if c["a"] is None:\n\n'
            f'{TAB * 1}include: "a"\n\n'
            'elif myobj.attr == "b":\n\n'
            f'{TAB * 1}include: "b"\n\n'
            'elif len(c["c"]) == 3:\n\n'
            f'{TAB * 1}include: "c"\n'
        )
        assert formatter.get_formatted() == expected

    def test_nested_snakecode_python_else_does_not_fail(self):
        snakecode = (
            'if c["a"] is None:\n\n'
            f"{TAB * 1}rule a:\n"
            f'{TAB * 2}shell:""\n\n\n'
            "else:\n"  # All python from here
            f'{TAB * 1}var = "b"\n'
        )
        expected = (
            'if c["a"] is None:\n\n'
            f"{TAB * 1}rule a:\n"
            f"{TAB * 2}shell:\n"
            f'{TAB * 3}""\n\n'
            "else:\n"  # All python from here
            f'{TAB * 1}var = "b"\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == expected

    def test_multiple_rules_inside_python_code(self):
        formatter = setup_formatter(
            "if condition:\n"
            f"{TAB * 1}rule a:\n"
            f'{TAB * 2}wrapper: "a"\n'
            f"{TAB * 1}rule b:\n"
            f'{TAB * 2}script: "b"'
        )
        expected = (
            "if condition:\n\n"
            f"{TAB * 1}rule a:\n"
            f"{TAB * 2}wrapper:\n"
            f'{TAB * 3}"a"\n\n'
            f"{TAB * 1}rule b:\n"
            f"{TAB * 2}script:\n"
            f'{TAB * 3}"b"\n'
        )
        assert formatter.get_formatted() == expected

    def test_indented_consecutive_snakemake_directives(self):
        snakecode = (
            'if config["load"]:\n\n'
            f'{TAB * 1}include: "module_a.smk"\n'
            f'{TAB * 1}include: "module_b.smk"\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_spaced_out_consecutive_dedented_directive(self):
        snakecode = (
            'if config["load"]:\n\n'
            f'{TAB * 1}include: "module_a.smk"\n\n'
            f"else:\n\n"
            f'{TAB * 1}include: "module_b.smk"\n\n\n'
            f'include: "other.smk"\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_comment_support_after_python_code(self):
        snakecode = (
            'if config["a"]:\n\n'
            f'{TAB * 1}include: "module_a.smk"\n\n\n'
            f'# include: "module_b.smk"\n\n\n'
            f'if config["c"]:\n\n'
            f'{TAB * 1}include: "module_c.smk"\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_nested_if_statements_with_comments_and_snakecode_inside(self):
        """https://github.com/snakemake/snakefmt/issues/126"""
        snakecode = (
            "# first standalone comment\n"
            "if True:\n"
            f"{TAB * 1}if True:\n\n"
            f"{TAB * 2}ruleorder: __a_ruleorder_and__  # inline comment\n"
            "\n"
            f"{TAB * 1}# second standalone comment\n"
            f'{TAB * 1}var = "anything really"\n\n'
            f"else:\n\n"
            f"{TAB * 1}# third standalone comment\n"
            f"{TAB * 1}ruleorder: some_other_order\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_nested_if_statements_with_comments_and_snakecode_inside2(self):
        """https://github.com/snakemake/snakefmt/pull/136#issuecomment-1125130038"""
        snakecode = (
            "if True:\n\n"
            f"{TAB * 1}ruleorder: A > B\n"
            "\n"
            f"{TAB * 1}mylist = []  # inline comment\n"
            f'{TAB * 1}mystr = "a"  # inline comment\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_nested_if_statements_with_comments_and_snakecode_inside3(self):
        """https://github.com/snakemake/snakefmt/pull/136#issuecomment-1132845522"""
        snakecode = (
            "if True:\n\n"
            f"{TAB * 1}rule with_run_directive:\n"
            f"{TAB * 2}output:\n"
            f'{TAB * 3}"test.txt",\n'
            f"{TAB * 2}run:\n"
            f"{TAB * 3}if True:\n"
            f'{TAB * 4}print("this line is in the error")\n'
            "\n"
            f'{TAB * 1}print("the indenting on this line matters")\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_nested_if_statements_with_function_and_snakecode_inside(self):
        """https://github.com/snakemake/snakefmt/pull/136#issuecomment-1125130038"""
        snakecode = (
            "if True:\n\n"
            f"{TAB * 1}ruleorder: A > B\n\n"
            f"{TAB * 1}def myfunc():\n"
            f"{TAB * 2}pass\n"
            "\n"
            f"{TAB * 1}mylist = []\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_nested_ifelse_statements(self):
        snakecode = (
            'if config["a"] is None:\n\n'
            f'{TAB * 1}include: "module_a_none.smk"\n\n'
            f"else:\n"
            f'{TAB * 1}if config["b"] is None:\n\n'
            f'{TAB * 2}include: "module_b.smk"\n\n'
            f"{TAB * 1}else:\n\n"
            f'{TAB * 2}include: "module_c.smk"\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_nested_ifelse_statements_multiple_python_lines(self):
        snakecode = (
            'if config["a"] is None:\n'
            f"{TAB * 1}a = 1\n\n"
            f'{TAB * 1}include: "module_a_none.smk"\n\n'
            f"else:\n"
            f'{TAB * 1}if config["b"] is None:\n\n'
            f'{TAB * 2}include: "module_b.smk"\n\n'
            f"{TAB * 1}else:\n"
            f"{TAB * 2}b = 0\n\n"
            f'{TAB * 2}include: "module_c.smk"\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode


class TestStringFormatting:
    """Naming: tpq = triple quoted string"""

    def test_param_with_string_mixture_retabbed_and_string_normalised(self):
        snakecode = (
            "rule a:\n"
            f"{TAB * 1}message:\n"
            f'{TAB * 2}"""Hello"""\n'
            f"{TAB * 2}'''    a string'''\n"
            f'{TAB * 3}"World"\n'
            f'{TAB * 3}"""    Yes"""\n'
        )
        expected = (
            "rule a:\n"
            f"{TAB * 1}message:\n"
            f'{TAB * 2}"""Hello"""\n'
            f'{TAB * 2}"""    a string"""\n'  # Quotes normalised
            f'{TAB * 2}"World"\n'
            f'{TAB * 2}"""    Yes"""\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == expected

    def test_keyword_with_tpq_inside_expression_left_alone(self):
        snakecode = (
            "rule test:\n" f"{TAB * 1}run:\n" f'{TAB * 2}shell(f"""shell stuff""")\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_rf_string_tpq_supported(self):
        """Deliberately tests for consecutive r/f strings and with
        single or double quotes"""
        for preceding in {"r", "f"}:
            snakecode = (
                "rule top:\n"
                f"{TAB * 1}shell:\n"
                f'{TAB * 2}{preceding}"""\n'
                f"{TAB * 2}Multi_line\n"
                f'{TAB * 2}"""\n'
                f'{TAB * 2}{preceding}"""\n'
                f"{TAB * 2}Other multi_line\n"
                f'{TAB * 2}"""\n'
            )
            assert setup_formatter(snakecode).get_formatted() == snakecode
            snakecode2 = snakecode.replace('"""', "'''")
            assert setup_formatter(snakecode2).get_formatted() == snakecode

    def test_tpq_alignment_and_keep_relative_indenting(self):
        snakecode = '''
rule a:
  shell:
    """Starts here
  Hello
    World
  \t\tTabbed
    """
'''
        formatter = setup_formatter(snakecode)

        expected = f'''
rule a:
{TAB * 1}shell:
{TAB * 2}"""Starts here
{TAB * 0}  Hello
{TAB * 1}World
{TAB * 2}  Tabbed
{TAB * 1}"""
'''
        assert formatter.get_formatted() == expected

    def test_tpq_alignment_and_keep_relative_indenting_for_r_string(self):
        snakecode = '''rule one:
    output:
        out_file="out.txt",
    shell:
        r"""
cat <<'EOF'> tmp.txt

touch {output}

EOF
bash tmp.txt
        """
'''
        formatter = setup_formatter(snakecode)

        assert formatter.get_formatted() == snakecode

    def test_tpq_alignment_and_keep_relative_indenting_for_multiline_string(self):
        snakecode = (
            "rule a:\n"
            f'{TAB * 1}shell: """\n'
            f'{TAB * 2}python -c "\n'
            f"{TAB * 0}if True:\n"
            f"{TAB * 1}print('Hello, world!')\n"
            f'{TAB * 2}"""'
        )
        formatter = setup_formatter(snakecode)
        expected = (
            "rule a:\n"
            f"{TAB * 1}shell:\n"
            f'{TAB * 2}"""\n'
            f'{TAB * 2}python -c "\n'
            f"{TAB * 0}if True:\n"
            f"{TAB * 1}print('Hello, world!')\n"
            f'{TAB * 2}"""\n'
        )

        assert formatter.get_formatted() == expected

    def test_single_quoted_multiline_string_proper_tabbing(self):
        snakecode = f"""
rule a:
{TAB * 1}shell:
{TAB * 2}"(kallisto quant \\
        --pseudobam \\
        input > output) \\
        2> log.stderr"
"""
        formatter = setup_formatter(snakecode)
        expected = f"""
rule a:
{TAB * 1}shell:
{TAB * 2}"(kallisto quant \\
{TAB * 2}--pseudobam \\
{TAB * 2}input > output) \\
{TAB * 2}2> log.stderr"
"""
        assert formatter.get_formatted() == expected

    def test_docstrings_get_retabbed_for_snakecode_only(self):
        """Black only retabs the first tpq in a docstring."""
        snakecode = '''def f():
  """Does not do
  much
"""
  pass


rule a:
  """The rule a
"""
  message:
    "a"
'''
        formatter = setup_formatter(snakecode)
        expected = f'''def f():
{TAB * 1}"""Does not do
    much"""
{TAB * 1}pass


rule a:
{TAB * 1}"""The rule a
{TAB * 0}"""
{TAB * 1}message:
{TAB * 2}"a"
'''
        assert formatter.get_formatted() == expected

    def test_tpq_inside_run_block(self):
        snakecode = '''rule cutadapt:
    input:
        "a.txt",
    output:
        "b.txt",
    run:
        if True:
            shell(
                """
            cutadapt \
                -m 30 \
                {input} \
                -o {output}
            """
            )
        else:
            shell(
                """
            cutadapt \
                {input} \
                -o {output}
            """
            )
'''
        formatter = setup_formatter(snakecode)

        assert formatter.get_formatted() == snakecode


class TestReformatting_SMK_BREAK:
    """
    Cases where snakemake v5.13.0 raises errors, but snakefmt reformats
    such that snakemake then runs fine
    """

    def test_key_value_parameter_repositioning(self):
        """Key/val params can occur before positional params"""
        formatter = setup_formatter(
            f"rule a:\n" f"{TAB * 1}input:\n" f'{TAB * 2}a="b",\n' f'{TAB * 2}"c"\n'
        )
        expected = (
            f"rule a:\n" f"{TAB * 1}input:\n" f'{TAB * 2}"c",\n' f'{TAB * 2}a="b",\n'
        )
        assert formatter.get_formatted() == expected


class TestCommentTreatment:
    def test_comment_after_parameter_keyword_twonewlines(self):
        snakecode = 'include: "a"\n# A comment\n'
        formatter = setup_formatter(snakecode)
        expected = 'include: "a"\n\n\n# A comment\n'
        assert formatter.get_formatted() == expected

    def test_comment_after_keyword_kept(self):
        snakecode = "rule a:  # A comment \n" f"{TAB * 1}threads: 4\n"
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_comments_after_parameters_kept(self):
        snakecode = (
            f"rule a:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}"myparam",  # a comment\n'
            f'{TAB * 2}b="param2",  # another comment\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_comments_PEP8_spaced_and_aligned(self):
        snakecode = (
            f"rule a:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}"myparam",{COMMENT_SPACING * 2}# a comment\n'
            f"{TAB * 2}    # another comment\n"
        )
        expected = (
            f"rule a:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}"myparam",{COMMENT_SPACING}# a comment\n'
            f"{TAB * 2}# another comment\n"
        )

        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == expected

    def test_comment_outside_keyword_context_stays_untouched(self):
        snakecode = (
            f"rule a:\n" f"{TAB * 1}run:\n" f"{TAB * 2}f()\n\n\n" f"# A comment\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_comment_below_paramkeyword_stays_untouched(self):
        snakecode = (
            "rule all:\n"
            f"{TAB * 1}input:\n"
            f"{TAB * 2}# A list of inputs\n"
            f"{TAB * 2}elem1,  #The first elem\n"
            f"{TAB * 2}elem1,  #The second elem\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    @pytest.mark.xfail(
        reason="""This is non-trivial to implement, and black does no align the comments
        like this, but places them two spaces after each line. See #86."""
    )
    def test_aligned_comments_stay_untouched(self):
        snakecode = (
            "rule eval:                             # [hide]\n"
            f"{TAB * 1}output:                      # [hide]\n"
            f'{TAB * 2}directory("resources/eval"), # [hide]\n'
            f"{TAB * 1}wrapper:                     # [hide]\n"
            f'{TAB * 2}"master/bio/benchmark/eval"  # [hide]\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_comments_above_parameter_keyword_stay_untouched(self):
        snakecode = (
            "rule all:\n"
            f"{TAB * 1}params:\n"
            f'{TAB * 2}extra="",  # optional\n'
            f"{TAB * 1}# comment1 above resources\n"
            f"{TAB * 1}# comment2 above resources\n"
            f"{TAB * 1}resources:\n"
            f"{TAB * 2}mem_mb=1024,\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_inline_formatted_params_relocate_inline_comments(self):
        snakecode = (
            "include: # Include\n"
            f"{TAB * 1}file.txt\n\n\n"
            "rule all:\n"
            f"{TAB * 1}threads:  # Threads 1\n"
            f"{TAB * 2}8  # Threads 2\n"
        )
        expected = (
            "# Include\n"
            f"include: file.txt\n\n\n"
            "rule all:\n"
            f"{TAB * 1}# Threads 1\n"
            f"{TAB * 1}threads: 8  # Threads 2\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == expected

    def test_preceding_comments_in_inline_formatted_params_get_relocated(self):
        snakecode = (
            "rule all:\n"
            f"{TAB * 1}# Threads1\n"
            f"{TAB * 1}threads: # Threads2\n"
            f"{TAB * 2}# Threads3\n"
            f"{TAB * 2}8  # Threads 4\n"
        )
        expected = (
            "rule all:\n"
            f"{TAB * 1}# Threads1\n"
            f"{TAB * 1}# Threads2\n"
            f"{TAB * 1}# Threads3\n"
            f"{TAB * 1}threads: 8  # Threads 4\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == expected

    def test_no_inline_comments_stay_untouched(self):
        snakecode = (
            "rule all:\n"
            f"{TAB * 1}input:\n"
            f"{TAB * 2}p=2,\n"
            f"{TAB * 2}#comment1\n"
            f"{TAB * 2}#comment2\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_snakecode_after_indented_comment_does_not_get_unindented(self):
        """https://github.com/snakemake/snakefmt/issues/159#issue-1441174995"""
        snakecode = (
            'if config.get("s3_dst"):\n\n'
            f'{TAB * 1}include: "workflow/rule1.smk"\n'
            f'{TAB * 1}include: "workflow/rule2.smk"\n'
            f"{TAB * 1}# a comment\n"
            f"{TAB * 1}# further comment\n"
            f'{TAB * 1}include: "workflow/rule3.smk"\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_comments_after_params_maintain_indentation(self):
        """https://github.com/snakemake/snakefmt/issues/160"""
        snakecode = (
            "if True:\n\n"
            f'{TAB * 1}include: "workflow.smk"\n'
            "\n"
            f"{TAB * 1}# indented comment\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_comment_in_run_block_at_start(self):
        """https://github.com/snakemake/snakefmt/issues/169#issuecomment-1361067856"""
        snakecode = (
            "rule foo:\n"
            f"{TAB * 1}input:\n"
            f"{TAB * 2}[],\n"
            f"{TAB * 1}run:\n"
            f"{TAB * 2}# some comment\n"
            f"{TAB * 2}y = 1\n"
            f"{TAB * 2}if True:\n"
            f"{TAB * 3}x = 3\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_two_comments_in_rule_at_start(self):
        """https://github.com/snakemake/snakefmt/issues/169#issue-1505309440"""
        snakecode = (
            "if x:\n\n"
            f"{TAB * 1}rule a:\n"
            f"{TAB * 2}# test\n"
            f"{TAB * 2}# test\n"
            f"{TAB * 2}output:\n"
            f'{TAB * 3}touch("data/a.txt"),\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_two_comments_in_global_context(self):
        """https://github.com/snakemake/snakefmt/issues/169#issuecomment-1365540999"""
        snakecode = (
            'configfile: "config.yaml"\n\n\n'
            "# AAA\n"
            "# BBB\n\n"
            'BATCH = "20220202"\n'
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_comment_documenting_onstart(self):
        """https://github.com/snakemake/snakefmt/issues/169#issuecomment-1404268174"""
        snakecode = (
            "onstart:\n"
            f"{TAB * 1}# comment\n"
            f"{TAB * 1}shell(\n"
            f"{TAB * 2}f\"./bin/notify-on-start {{config.get('build_name', 'unknown')}} {{SLACK_TS_FILE}}\"\n"  # noqa: E501  due to readability of test
            f"{TAB * 1})\n"
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

    def test_repeated_parameter_keyword_no_spacing(self):
        """
        For keywords that expect a single parameter in the global context,
        (eg: 'configfile', 'include'), if they occur consecutively, do not
        double-space them.
        """
        global_single_param_keywords = [
            keyval[0]
            for keyval in SnakeGlobal.spec.items()
            if keyval[1].syntax is SingleParam
        ]
        snakecode = '{keyword_param}: "value1"\n{keyword_param}: "value2"\n'
        for keyword in global_single_param_keywords:
            replaced = snakecode.format(keyword_param=keyword)
            formatter = setup_formatter(replaced)
            assert formatter.get_formatted() == replaced

    def test_repeated_parameter_keyword_comment_in_between_no_spacing(self):
        snakecode = 'include: "a"\n# A comment\n # c2\ninclude: "b"\n'
        expected = 'include: "a"\n# A comment\n# c2\ninclude: "b"\n'
        assert setup_formatter(snakecode).get_formatted() == expected

    def test_repeated_parameter_keyword_spaced_comment_in_between_spacing(self):
        snakecode = 'include: "a"\n\n# A lone comment\n\ninclude: "b"\n'
        expected = 'include: "a"\n\n\n# A lone comment\n\n\ninclude: "b"\n'
        assert setup_formatter(snakecode).get_formatted() == expected

    def test_repeated_parameter_keyword_code_in_between_spacing(self):
        snakecode = 'include: "a"\n\n\nfoo = 2\n\n\ninclude: "b"\n'
        assert setup_formatter(snakecode).get_formatted() == snakecode

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
        formatter = setup_formatter('include: "a"\n\n\n\nconfigfile: "b"\n')
        expected = 'include: "a"\n\n\nconfigfile: "b"\n'

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

    def test_initial_comment_does_not_trigger_spacing(self):
        snakecode = (
            f"# load config\n" f"rule all:\n" f"{TAB * 1}input:\n" f"{TAB * 2}files,\n"
        )

        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == snakecode

    def test_comment_sticks_to_rule(self):
        snakecode = (
            "def p():\n"
            f"{TAB * 1}pass\n"
            f"#My rule a\n"
            f"rule a:\n"
            f"{TAB * 1}threads: 1\n"
        )
        formatter = setup_formatter(snakecode)
        expected = (
            "def p():\n"
            f"{TAB * 1}pass\n\n\n"
            f"# My rule a\n"
            f"rule a:\n"
            f"{TAB * 1}threads: 1\n"
        )
        assert formatter.get_formatted() == expected

    def test_keyword_disjoint_comment_stays_keyword_disjoint(self):
        snakecode = (
            "def p():\n" f"{TAB * 1}pass\n" f"#A lone comment\n\n" f'include: "a"\n'
        )
        formatter = setup_formatter(snakecode)
        expected = (
            "def p():\n"
            f"{TAB * 1}pass\n\n\n"  # Newlined by black
            f"# A lone comment\n\n\n"  # Remains lone comment
            f'include: "a"\n'
        )
        assert formatter.get_formatted() == expected

    def test_buffer_with_lone_comment(self):
        snakecode = 'include: "a"\n# A comment\nreport: "b"\n'
        expected = 'include: "a"\n\n\n# A comment\nreport: "b"\n'
        assert setup_formatter(snakecode).get_formatted() == expected

    def test_comment_inside_python_code_sticks_to_rule(self):
        snakecode = f"if p:\n" f"{TAB * 1}# A comment\n" f'{TAB * 1}include: "a"\n'
        expected = f"if p:\n\n" f"{TAB * 1}# A comment\n" f'{TAB * 1}include: "a"\n'
        assert setup_formatter(snakecode).get_formatted() == expected

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

    def test_spacing_in_python_code_after_keywrod_not_altered(self):
        """https://github.com/snakemake/snakefmt/issues/149"""
        snakecode = (
            "if not config:\n\n"
            f'{TAB * 1}configfile: "config.yaml"\n\n\n'
            'build_dir = "results"\n\n'
            'auspice_dir = "auspice"\n'
        )

        formatter = setup_formatter(snakecode)

        assert formatter.get_formatted() == snakecode


class TestLineWrapping:
    def test_long_line_within_rule_indentation_taken_into_account(self):
        snakecode = (
            f"rule coverage_report:\n"
            f"{TAB * 1}input:\n"
            f"{TAB * 2}lineage=expand(\n"
            f'{TAB * 3}str(report_dir / "lineage_assignment" / "{{sample}}.lineage.csv"), sample=samples\n'  # noqa: E501  due to readability of test
            f"{TAB * 2}),\n"
            f"{TAB * 2}subsample_logs=list(subsample_logfiles),"
        )
        line_length = 88
        formatter = setup_formatter(snakecode, line_length)
        actual = formatter.get_formatted()
        expected = (
            f"rule coverage_report:\n"
            f"{TAB * 1}input:\n"
            f"{TAB * 2}lineage=expand(\n"
            f'{TAB * 3}str(report_dir / "lineage_assignment" / "{{sample}}.lineage.csv"),\n'  # noqa: E501  due to readability of test
            f"{TAB * 3}sample=samples,\n"
            f"{TAB * 2}),\n"
            f"{TAB * 2}subsample_logs=list(subsample_logfiles),\n"
        )

        assert actual == expected

    def test_multiline_parameter_list_gets_wrapped(self):
        """issue 111"""
        snakecode = (
            f"rule r:\n"
            f"{TAB * 1}input:\n"
            f"{TAB * 2}expand(\n"
            f'{TAB * 3}os.path.join("dir1"),\n'
            f"{TAB * 2})+\n"
            f"{TAB * 2}[\n"
            f'{TAB * 2}"dirname",\n'
            f"{TAB * 2}],\n"
        )
        expected = (
            f"rule r:\n"
            f"{TAB * 1}input:\n"
            f"{TAB * 2}expand(\n"
            f'{TAB * 3}os.path.join("dir1"),\n'
            f"{TAB * 2})\n"
            f"{TAB * 2}+ [\n"
            f'{TAB * 3}"dirname",\n'
            f"{TAB * 2}],\n"
        )
        formatter = setup_formatter(snakecode)
        assert formatter.get_formatted() == expected

    def test_indenting_long_param_lines(self):
        """https://github.com/snakemake/snakefmt/issues/124"""
        snakecode = (
            "rule a:\n"
            f"{TAB*1}output:\n"
            f'{TAB*2}"foo",\n'
            f"{TAB*1}params:\n"
            f"{TAB*2}datasources=(\n"
            f'{TAB*3}"-s {{}}".format(" ".join(config["annotations"]["dgidb"]["datasources"]))\n'  # noqa: E501
            f'{TAB*3}if config["annotations"]["dgidb"].get("datasources", "")\n'
            f'{TAB*3}else ""\n'
            f"{TAB*2}),\n"
        )
        formatter = setup_formatter(snakecode)

        assert formatter.get_formatted() == snakecode

    def test_indented_block_with_functions_and_rule(self):
        """https://github.com/snakemake/snakefmt/issues/124#issuecomment-986845398"""
        snakecode = (
            "if True:\n\n"
            f"{TAB*1}def func1():\n"
            f'''{TAB*2}"""docstring"""\n'''
            f"{TAB*2}pass\n\n"
            f"{TAB*1}rule foo:\n"
            f"{TAB*2}shell:\n"
            f'{TAB*3}"echo bar"\n\n'
            f"{TAB*1}def func2():\n"
            f'''{TAB*2}"""this function should stay indented"""\n'''
            f"{TAB*2}pass\n"
        )
        formatter = setup_formatter(snakecode)

        assert formatter.get_formatted() == snakecode
