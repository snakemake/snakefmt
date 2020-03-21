from io import StringIO

import pytest

from snakefmt.formatter import Formatter
from snakefmt.parser.parser import Snakefile


class TestFormatter:
    def test_emptyInput_emptyOutput(self):
        stream = StringIO()
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = ""

        assert actual == expected

    def test_configfileLineWithSingleQuotes_returnsDoubleQuotes(self):
        stream = StringIO("configfile: 'foo.yaml'")
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = 'configfile: "foo.yaml"\n'

        assert actual == expected

    def test_commented_snakemake_syntax_we_dont_format_but_black_does(self):
        stream = StringIO("#configfile: 'foo.yaml'")
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = "# configfile: 'foo.yaml'\n"

        assert actual == expected

    def test_simple_rule_one_input(self):
        stream = StringIO("rule a:\n\tinput: 'foo.txt'")
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = """rule a:
\tinput: 
\t\t\"foo.txt\", \n"""

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
\tinput: 
\t\tlambda wildcards: foo(wildcards), \n"""

        assert actual == expected

    def test_lambda_function_as_parameter_for_parameter(self):
        stream = StringIO(
            """rule a: 
\tinput: 'foo.txt'
\tresources:
\t\tmem_mb = lambda wildcards, attempt: attempt * 1000"""
        )
        smk = Snakefile(stream)
        formatter = Formatter(smk)

        actual = formatter.get_formatted()
        expected = """rule a:
\tinput: 
\t\t\"foo.txt\"
\tresources:
\t\tmem_mb = lambda wildcards, attempt: attempt * 1000, \n"""

        assert actual == expected
