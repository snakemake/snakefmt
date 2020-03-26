"""
Examples where we raise errors,
 but snakemake does not are listed as 'SMK_NOBREAK'
"""
from io import StringIO

import pytest

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
from snakefmt.formatter import Formatter
from snakefmt.parser.parser import Snakefile


class TestKeywordSyntaxErrors:
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
        The keyword lives in the 'base' space, so could also be interpreted as Python code.
        In that case black will complain of invalid python and not format it.
        """
        with pytest.raises(InvalidPython):
            stream = StringIO("Rule a: 3")
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_consecutive_duplicate_keyword_SMK_NOBREAK(self):
        with pytest.raises(DuplicateKeyWordError, match="threads"):
            stream = StringIO("rule a:" "\n\tthreads: 3" "\n\tthreads: 5")
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_non_consecutive_duplicate_keyword_SMK_NOBREAK(self):
        with pytest.raises(DuplicateKeyWordError, match="rule a"):
            stream = StringIO("rule a:\n" '\tinput: "a"\n' "rule a:\n" '\tinput:"b"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

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


class TestParamSyntaxErrors:
    def test_key_value_no_key(self):
        with pytest.raises(InvalidParameterSyntax, match="Operator ="):
            stream = StringIO("rule a:" '\n\tinput: = "file.txt"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_key_value_invalid_key(self):
        with pytest.raises(InvalidParameterSyntax, match="Invalid key"):
            stream = StringIO("rule a:" '\n\tinput: \n\t\t2 = "file.txt"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_too_many_params(self):
        with pytest.raises(TooManyParameters, match="benchmark"):
            stream = StringIO("rule a:" '\n\tbenchmark: "f1.txt", "f2.txt"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_positional_required(self):
        with pytest.raises(InvalidParameter, match="container .* positional"):
            stream = StringIO("rule a: \n" '\tcontainer: a = "envs/sing.img"')
            snakefile = Snakefile(stream)
            Formatter(snakefile)


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
