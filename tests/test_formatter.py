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
