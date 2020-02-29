import re
import pytest

from snakefmt.snakefmt import construct_regex


class TestConstructRegex:
    def test_noNewline_returnsCompiledRegex(self):
        regex = r"\.smk$"

        actual = construct_regex(regex)
        expected = re.compile(regex)

        assert actual == expected

    def test_containsNewline_returnsCompiledRegexWithMultilineSetting(self):
        regex = r"""
(
  /(
      \.eggs         # exclude a few common directories in the
    | \.git          # root of the project
    | \.snakemake
  )/
)
"""

        actual = construct_regex(regex)
        expected = re.compile(regex, re.MULTILINE | re.VERBOSE)

        assert actual == expected

    def test_invalidRegex_raisesError(self):
        regex = r"?"

        with pytest.raises(re.error):
            construct_regex(regex)
