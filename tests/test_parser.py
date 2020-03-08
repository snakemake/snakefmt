"""
Examples where we raise errors,
 but snakemake does not are listed as 'SMK_NOBREAK'
"""
import pytest
from snakefmt.snakefmt import Snakefile, Formatter
from io import StringIO
from snakefmt.exceptions import (
    InvalidPython,
    DuplicateKeyWordError,
    EmptyContextError,
    NoParametersError,
)


class TestKeywordSyntaxErrors:
    def test_nocolon(self):
        with pytest.raises(SyntaxError, match="Colon expected"):
            stream = StringIO("rule a")
            snakefile = Snakefile(stream)
            Formatter(snakefile)

    def test_no_newline_in_keyword_context_SMK_NOBREAK(self):
        with pytest.raises(SyntaxError, match="Newline expected"):
            stream = StringIO('rule a: input: "input_file"')
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

    def test_duplicate_keyword_SMK_NOBREAK(self):
        with pytest.raises(DuplicateKeyWordError, match="threads"):
            stream = StringIO("rule a:" "\n\tthreads: 3" "\n\tthreads: 5")
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


class TestIndentationErrors:
    pass
