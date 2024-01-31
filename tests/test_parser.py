"""Syntax validation tests

Examples where we raise errors but snakemake does not are listed as 'SMK_NOBREAK'
"""

from io import StringIO

import pytest

from snakefmt.exceptions import (
    EmptyContextError,
    InvalidParameter,
    InvalidParameterSyntax,
    InvalidPython,
    NoParametersError,
    TooManyParameters,
)
from snakefmt.formatter import TAB
from tests import Formatter, Snakefile, setup_formatter


class TestSnakefileTokenizer:
    text = f"rule a:\n{TAB * 1}threads: 8"

    def test_snakefile_sequential_parsing(self):
        istream = StringIO(self.text)
        expected_sequence = istream.read().split()
        istream.seek(0)
        snakefile = Snakefile(istream)
        for expected_word in expected_sequence:
            try:
                parsed_word = next(snakefile).string
                assert expected_word == parsed_word
            except Exception:
                break

    def test_snakefile_staggered_parsing(self):
        snakefile = Snakefile(StringIO(self.text))
        token_buffer = list()
        next(snakefile)
        for _ in range(3):
            token_buffer.append(next(snakefile))
        for token in reversed(token_buffer):
            snakefile.denext(token)
        result_sequence = list()
        for _ in range(3):
            result_sequence.append(next(snakefile).string)
        expected_sequence = ["a", ":", "\n"]
        assert expected_sequence == result_sequence


class TestKeywordSyntax:
    def test_nocolon(self):
        with pytest.raises(SyntaxError, match="Colon.*expected"):
            setup_formatter("rule a")

    def test_no_newline_in_keyword_context_SMK_NOBREAK(self):
        with pytest.raises(SyntaxError, match="Newline expected"):
            setup_formatter('rule a: input: "input_file"')

    def test_keyword_cannot_be_named(self):
        with pytest.raises(SyntaxError, match="Colon.*expected"):
            setup_formatter('workdir a: "/to/dir"')

    def test_invalid_name_for_keyword(self):
        with pytest.raises(SyntaxError, match=".*checkpoint.*valid identifier"):
            setup_formatter("checkpoint (): \n" '\tinput: "a"')

    def test_explicitly_unrecognised_keyword(self):
        with pytest.raises(SyntaxError, match="Unrecognised keyword"):
            setup_formatter("rule a:" "\n\talien_keyword: 3")

    def test_implicitly_unrecognised_keyword(self):
        """
        The keyword lives in the 'base' space, so could also be interpreted as Python
        code.
        In that case black will complain of invalid python and not format it.
        """
        with pytest.raises(InvalidPython):
            setup_formatter(f"role a: \n" f'{TAB * 1}input: "b"')

    def test_duplicate_anonymous_rule_passes(self):
        setup_formatter(
            "rule:\n" f"{TAB * 1}threads: 4\n" "rule:\n" f"{TAB * 1}threads: 4\n"
        )

    def test_authorised_duplicate_keyword_passes(self):
        setup_formatter('include: "a"\n' 'include: "b"\n')

    def test_empty_keyword_SMK_NOBREAK(self):
        with pytest.raises(EmptyContextError, match="rule"):
            setup_formatter("rule a:")

    def test_empty_keyword_2(self):
        with pytest.raises(NoParametersError, match="threads"):
            setup_formatter("rule a:" "\n\tthreads:")

    def test_empty_keyword_3(self):
        with pytest.raises(NoParametersError, match="message"):
            setup_formatter("rule a:" "\n\tthreads: 3" "\n\tmessage:")


class TestUseRuleKeywordSyntax:
    def test_rule_from_module_passes(self):
        setup_formatter("use rule a from mymodule")

    def test_rule_modified_from_rule_passes(self):
        setup_formatter("use rule a as b with:\n" f"{TAB * 1}threads: 4")

    def test_renamed_rule_from_module_passes(self):
        setup_formatter("use rule a from mymodule as mymodule_a")
        setup_formatter("use rule * from mymodule as mymodule_*")

    def test_modified_rule_from_module_passes(self):
        setup_formatter("use rule a from mymodule with:\n" f"{TAB * 1}threads: 4")
        setup_formatter(
            "use rule b from mymodule as my_b with:\n"
            f"{TAB * 1}output:\n"
            f'{TAB * 2}"new_output"'
        )

    def test_invalid_syntax_throws(self):
        with pytest.raises(SyntaxError, match="not of form"):
            setup_formatter("use rule b from *")

        with pytest.raises(SyntaxError, match="not of form"):
            setup_formatter("use rule b from module as with:")

    def test_use_rule_cannot_use_rule_specific_keywords(self):
        with pytest.raises(SyntaxError, match="Unrecognised keyword"):
            setup_formatter(
                "use rule a from mymodule with:\n" f'{TAB * 1}shell: "mycommand"'
            )


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

    def test_key_value_no_value_fails(self):
        """https://github.com/snakemake/snakefmt/issues/125"""
        snakecode = (
            "rule foo:\n"
            f"{TAB * 1}input:\n"
            f'{TAB * 2}bar="file.txt",\n'
            f"{TAB * 2}baz=\n"
        )
        with pytest.raises(NoParametersError, match="baz"):
            setup_formatter(snakecode)


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

    def test_multiline_correctly_passed_to_black(self):
        snake = """rule multiqc_report:
    input:
        fastqc_pe=expand(
            os.path.join(
                config["output_dir"], "samples", "{sample}", "fastqc", "{mate}"
            ),
            sample=[
                i
                for i in pd.unique(
                    samples_table[samples_table["seqmode"] == "pe"].index.values
                )
            ],
            mate="fq2",
        ),
"""
        setup_formatter(snake)
