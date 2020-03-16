"""
Examples where we raise errors,
 but snakemake does not are listed as 'SMK_NOBREAK'
"""
from io import StringIO

import pytest

from snakefmt.exceptions import (
    DuplicateKeyWordError,
    EmptyContextError,
    InvalidParameter,
    InvalidParameterSyntax,
    InvalidPython,
    NoParametersError,
    TooManyParameters,
)
from snakefmt.parser.parser import Parser, Snakefile


class TestKeywordSyntaxErrors:
    def test_nocolon(self):
        with pytest.raises(SyntaxError, match="Colon expected"):
            stream = StringIO("rule a")
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_no_newline_in_keyword_context_SMK_NOBREAK(self):
        with pytest.raises(SyntaxError, match="Newline expected"):
            stream = StringIO('rule a: input: "input_file"')
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_explicitly_unrecognised_keyword(self):
        with pytest.raises(SyntaxError, match="Unrecognised keyword"):
            stream = StringIO("rule a:" "\n\talien_keyword: 3")
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_implicitly_unrecognised_keyword(self):
        """
        The keyword lives in the 'base' space, so could also be interpreted as Python code.
        In that case black will complain of invalid python and not format it.
        """
        with pytest.raises(InvalidPython):
            stream = StringIO("Rule a: 3")
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_duplicate_keyword_SMK_NOBREAK(self):
        with pytest.raises(DuplicateKeyWordError, match="threads"):
            stream = StringIO("rule a:" "\n\tthreads: 3" "\n\tthreads: 5")
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_empty_keyword_SMK_NOBREAK(self):
        with pytest.raises(EmptyContextError, match="rule"):
            stream = StringIO("rule a:")
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_empty_keyword_2(self):
        with pytest.raises(NoParametersError, match="threads"):
            stream = StringIO("rule a:" "\n\tthreads:")
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_empty_keyword_3(self):
        with pytest.raises(NoParametersError, match="message"):
            stream = StringIO("rule a:" "\n\tthreads: 3" "\n\tmessage:")
            snakefile = Snakefile(stream)
            Parser(snakefile)


class TestParamSyntaxErrors:
    def test_key_value_no_key(self):
        with pytest.raises(InvalidParameterSyntax, match="Operator ="):
            stream = StringIO("rule a:" '\n\tinput: = "file.txt"')
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_key_value_invalid_key(self):
        with pytest.raises(InvalidParameterSyntax, match="Invalid key"):
            stream = StringIO("rule a:" '\n\tinput: \n\t\t2 = "file.txt"')
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_too_many_params(self):
        with pytest.raises(TooManyParameters, match="benchmark"):
            stream = StringIO("rule a:" '\n\tbenchmark: "f1.txt", "f2.txt"')
            snakefile = Snakefile(stream)
            Parser(snakefile)

    @pytest.mark.xfail
    def test_string_required(self):
        with pytest.raises(InvalidParameter, match="message .*str"):
            stream = StringIO('b = "test"\n' "rule a: \n" "\tmessage: b")
            snakefile = Snakefile(stream)
            Parser(snakefile)

    @pytest.mark.xfail
    def test_string_required2(self):
        with pytest.raises(InvalidParameter, match="envmodules .*str"):
            stream = StringIO('rule a: \n\tenvmodules: 3, "bio/module"')
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_positional_required(self):
        with pytest.raises(InvalidParameter, match="singularity .* positional"):
            stream = StringIO('rule a: \n\tsingularity: a = "envs/sing.img"')
            snakefile = Snakefile(stream)
            Parser(snakefile)


class TestIndentationErrors:
    def test_keyword_over_indentation(self):
        with pytest.raises(IndentationError, match="benchmark.* over-indented"):
            stream = StringIO(
                'rule a: \n\tsingularity: \n\t\t"envs/sing.img" \n\t\t\tbenchmark: "bench.txt"'
            )
            snakefile = Snakefile(stream)
            Parser(snakefile)

    def test_keyword_indented_at_parameter_level(self):
        with pytest.raises(InvalidParameterSyntax, match="output:"):
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
            Parser(snakefile)
