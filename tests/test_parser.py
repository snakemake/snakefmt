"""Syntax validation tests

Examples where we raise errors but snakemake does not are listed as 'SMK_NOBREAK'
"""
from io import StringIO

import pytest

from tests import setup_formatter, Snakefile, Formatter
from snakefmt.exceptions import (
    InvalidPython,
    DuplicateKeyWordError,
    EmptyContextError,
    NoParametersError,
    TooManyParameters,
    InvalidParameter,
    InvalidParameterSyntax,
    NamedKeywordError,
)
from snakefmt.formatter import TAB


class TestKeywordSyntax:
    def test_nocolon(self):
        with pytest.raises(SyntaxError, match="Colon.*expected"):
            stream = StringIO("rule a")
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_no_newline_in_keyword_context_SMK_NOBREAK(self):
        with pytest.raises(SyntaxError, match="Newline expected"):
            stream = StringIO('rule a: input: "input_file"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_keyword_cannot_be_named(self):
        with pytest.raises(SyntaxError, match="Colon.*expected"):
            stream = StringIO('workdir a: "/to/dir"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_invalid_name_for_keyword(self):
        with pytest.raises(NamedKeywordError, match="Invalid name.*checkpoint"):
            stream = StringIO("checkpoint (): \n" '\tinput: "a"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_explicitly_unrecognised_keyword(self):
        with pytest.raises(SyntaxError, match="Unrecognised keyword"):
            stream = StringIO("rule a:" "\n\talien_keyword: 3")
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_implicitly_unrecognised_keyword(self):
        """
        The keyword lives in the 'base' space, so could also be interpreted as Python
        code.
        In that case black will complain of invalid python and not format it.
        """
        with pytest.raises(InvalidPython):
            stream = StringIO(f"role a: \n" f'{TAB * 1}input: "b"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_duplicate_rule_fails_SMK_NOBREAK(self):
        with pytest.raises(DuplicateKeyWordError, match="rule a"):
            stream = StringIO("rule a:\n" '\tinput: "a"\n' "rule a:\n" '\tinput:"b"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_authorised_duplicate_keyword_passes(self):
        setup_formatter('include: "a"\n' 'include: "b"\n')

    def test_empty_keyword_SMK_NOBREAK(self):
        with pytest.raises(EmptyContextError, match="rule"):
            stream = StringIO("rule a:")
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_empty_keyword_2(self):
        with pytest.raises(NoParametersError, match="threads"):
            stream = StringIO("rule a:" "\n\tthreads:")
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_empty_keyword_3(self):
        with pytest.raises(NoParametersError, match="message"):
            stream = StringIO("rule a:" "\n\tthreads: 3" "\n\tmessage:")
            snakefile = Snakefile(stream)
            Formatter(snakefile)


class TestParamSyntax:
    def test_key_value_no_key_fails(self):
        with pytest.raises(InvalidParameterSyntax, match="Operator ="):
            stream = StringIO("rule a:" '\n\tinput: = "file.txt"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_key_value_invalid_key_fails(self):
        with pytest.raises(InvalidParameterSyntax, match="Invalid key"):
            stream = StringIO("rule a:" '\n\tinput: \n\t\t2 = "file.txt"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_single_parameter_keyword_disallows_multiple_parameters(self):
        with pytest.raises(TooManyParameters, match="benchmark"):
            stream = StringIO("rule a:" '\n\tbenchmark: "f1.txt", "f2.txt"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_single_parameter_keyword_disallows_kwarg(self):
        with pytest.raises(InvalidParameter, match="container .* positional"):
            stream = StringIO("rule a: \n" '\tcontainer: a = "envs/sing.img"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_parameter_list_keyword_disallows_kwarg(self):
        with pytest.raises(InvalidParameterSyntax):
            snake_code = f"envvars:\n" f'{TAB * 1}"VAR1",' f'{TAB * 1}var2 = "VAR2"'
            setup_formatter(snake_code)

    def test_dictionary_unpacking_passes(self):
        snake_code = (
            f"rule a:\n"
            f'{TAB * 1}params: **config["params"]\n'
            f'{TAB * 1}shell: "mycommand {{params}}"'
        )
        setup_formatter(snake_code)


class TestIndentationErrors:
    def test_param_collating(self):
        "The keyword gets collated to the previous parameter value"
        with pytest.raises(InvalidParameterSyntax, match="benchmark"):
            stream = StringIO(
                "rule a: \n"
                "\tcontainer: \n"
                '\t\t"envs/sing.img"\n'
                '\t\t\tbenchmark: "bench.txt"'
            )
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_keyword_under_indentation(self):
        "The keyword gets interpreted as python code"
        with pytest.raises(InvalidPython, match="benchmark"):
            stream = StringIO(
                "rule a: \n"
                "\tcontainer: \n"
                '\t\t"envs/sing.img"\n'
                'benchmark: "bench.txt"'
                '\toutput: "b"'
            )
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_keyword_indented_at_parameter_level(self):
        with pytest.raises(InvalidParameterSyntax, match="output"):
            stream = StringIO(
                (
                    "rule a: \n"
                    "\tinput: \n"
                    '\t\t"f1", \n'
                    "\t\toutput: \n"
                    '\t\t\t"f2"'
                )
            )
            snakefile = Snakefile(stream)
            Formatter(snakefile)


class TestPythonCode:
    def test_invalid_python_code_fails(self):
        python_code = f"if invalid code here:\n" f"{TAB * 1}break"
        with pytest.raises(InvalidPython):
            setup_formatter(python_code)

    def test_invalid_python_code_preceding_nested_rule_fails(self):
        snakecode = (
            f"if invalid code here:\n" f"{TAB * 1}rule a:\n" f"{TAB * 2}threads: 1"
        )
        snakecode2 = f"def p:\n" f"{TAB * 1}rule a:\n" f"{TAB * 2}threads: 1"
        with pytest.raises(InvalidPython):
            setup_formatter(snakecode)
        with pytest.raises(InvalidPython):
            setup_formatter(snakecode2)

    def test_rules_inside_python_code_passes(self):
        snake = (
            f"if condition1:\n"
            f"{TAB * 1}if condition2:\n"
            f"{TAB * 2}rule a:\n"
            f'{TAB * 3}input:"in"\n'
        )
        setup_formatter(snake)

    def test_multicopy_rule_name_inside_python_code_passes(self):
        snake = (
            f"if condition1:\n"
            f"{TAB * 1}rule all:\n"
            f'{TAB * 2}wrapper:"a"\n'
            f"elif condition2:\n"
            f"{TAB * 1}rule all:\n"
            f'{TAB * 2}wrapper:"b"\n'
            f"else:\n"
            f"{TAB * 1}rule all:\n"
            f'{TAB * 2}wrapper:"c"'
        )
        setup_formatter(snake)

    def test_multicopy_parameter_keyword_inside_python_code_passes(self):
        snake = (
            f"if condition1:\n"
            f"{TAB * 1}if condition2:\n"
            f'{TAB * 2}configfile: "f1"\n'
            f"{TAB * 1}else:\n"
            f'{TAB * 2}configfile: "f2"\n'
        )
        setup_formatter(snake)

    def test_multicopy_rule_name_after_python_code_fails(self):
        snake = (
            f"if condition1:\n"
            f"{TAB * 1}rule all:\n"
            f'{TAB * 2}wrapper:"a"\n'
            f"rule b:\n"
            f'{TAB * 1}wrapper:"b"\n'
            f"rule b:\n"
            f'{TAB * 1}wrapper:"b"'
        )
        with pytest.raises(DuplicateKeyWordError):
            setup_formatter(snake)

    def test_snakecode_inside_run_directive_fails(self):
        snake_code = (
            f"rule a:\n"
            f"{TAB * 1}run:\n"
            f"{TAB * 2}if condition:\n"
            f"{TAB * 3}rule b:\n"
            f'{TAB * 4}input: "in"\n'
        )
        with pytest.raises(InvalidPython):
            setup_formatter(snake_code)
