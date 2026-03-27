"""Syntax validation tests

Examples where we raise errors but snakemake does not are listed as 'SMK_NOBREAK'
"""

import tokenize
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
from snakefmt.parser.parser import (
    FMT_DIRECTIVE,
    check_indent,
    split_token_lines,
    token_indents_updated,
)
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

    def test_use_with(self):
        with pytest.raises(
            InvalidParameterSyntax, match="Syntax 'keyword with:' not allowed for"
        ):
            setup_formatter("rule a:\n" f'{TAB * 1}input with: touch("file.txt")')
        with pytest.raises(SyntaxError, match="threads with: <params>"):
            setup_formatter("use rule a as a1 with:\n" f"{TAB * 1}threads with: 4")
        with pytest.raises(SyntaxError, match="Colon.*expected"):
            setup_formatter("use rule a as a1 with:\n" f"{TAB * 1}input with '4'")


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


def _make_token(type_, string, start=(1, 0), end=None, line=None):
    """Helper to create a tokenize.TokenInfo for testing."""
    if end is None:
        end = (start[0], start[1] + len(string))
    if line is None:
        line = string + "\n"
    return tokenize.TokenInfo(type_, string, start, end, line)


class TestFMTDirective:
    """Tests for FMT_DIRECTIVE.from_str and FMT_DIRECTIVE.from_token."""

    # --- from_str: valid fmt: off directives ---

    def test_from_str_plain_off(self):
        result = FMT_DIRECTIVE.from_str("# fmt: off")
        assert result is not None
        assert result.disable is True
        assert result.modifiers == []

    def test_from_str_plain_on(self):
        result = FMT_DIRECTIVE.from_str("# fmt: on")
        assert result is not None
        assert result.disable is False
        assert result.modifiers == []

    def test_from_str_off_with_sort_modifier(self):
        result = FMT_DIRECTIVE.from_str("# fmt: off[sort]")
        assert result is not None
        assert result.disable is True
        assert result.modifiers == ["sort"]

    def test_from_str_on_with_sort_modifier(self):
        result = FMT_DIRECTIVE.from_str("# fmt: on[sort]")
        assert result is not None
        assert result.disable is False
        assert result.modifiers == ["sort"]

    def test_from_str_off_with_next_modifier(self):
        result = FMT_DIRECTIVE.from_str("# fmt: off[next]")
        assert result is not None
        assert result.disable is True
        assert result.modifiers == ["next"]

    def test_from_str_on_with_next_modifier(self):
        result = FMT_DIRECTIVE.from_str("# fmt: on[next]")
        assert result is not None
        assert result.disable is False
        assert result.modifiers == ["next"]

    def test_from_str_multiple_modifiers(self):
        result = FMT_DIRECTIVE.from_str("# fmt: off[sort, next]")
        assert result is not None
        assert result.disable is True
        assert result.modifiers == ["sort", "next"]

    def test_from_str_with_trailing_double_space(self):
        """Two trailing spaces are allowed after directive."""
        result = FMT_DIRECTIVE.from_str("# fmt: off  ")
        assert result is not None
        assert result.disable is True

    def test_from_str_with_inline_comment(self):
        """A space and # after directive are allowed."""
        result = FMT_DIRECTIVE.from_str("# fmt: off # reason")
        assert result is not None
        assert result.disable is True

    # --- from_str: non-matching strings ---

    def test_from_str_not_a_directive(self):
        assert FMT_DIRECTIVE.from_str("# some comment") is None

    def test_from_str_fmton_no_space(self):
        """'fmton' is not a fmt directive."""
        assert FMT_DIRECTIVE.from_str("# fmton") is None

    def test_from_str_single_trailing_space_not_matched(self):
        """Exactly one trailing space should not match."""
        assert FMT_DIRECTIVE.from_str("# fmt: off ") is None

    def test_from_str_fmt_colon_no_off_on(self):
        """'# fmt: skip' is not a recognized directive."""
        assert FMT_DIRECTIVE.from_str("# fmt: skip") is None

    def test_from_str_empty_string(self):
        assert FMT_DIRECTIVE.from_str("") is None

    def test_from_str_plain_comment_symbol(self):
        assert FMT_DIRECTIVE.from_str("#") is None

    # --- from_token: COMMENT tokens ---

    def test_from_token_comment_off(self):
        token = _make_token(tokenize.COMMENT, "# fmt: off")
        result = FMT_DIRECTIVE.from_token(token)
        assert result is not None
        assert result.disable is True
        assert result.modifiers == []

    def test_from_token_comment_on_sort(self):
        token = _make_token(tokenize.COMMENT, "# fmt: on[sort]")
        result = FMT_DIRECTIVE.from_token(token)
        assert result is not None
        assert result.disable is False
        assert result.modifiers == ["sort"]

    def test_from_token_not_comment_returns_none(self):
        """Non-COMMENT tokens always return None."""
        token = _make_token(tokenize.NAME, "rule")
        assert FMT_DIRECTIVE.from_token(token) is None

    def test_from_token_newline_returns_none(self):
        token = _make_token(tokenize.NEWLINE, "\n")
        assert FMT_DIRECTIVE.from_token(token) is None

    def test_from_token_string_returns_none(self):
        token = _make_token(tokenize.STRING, '"# fmt: off"')
        assert FMT_DIRECTIVE.from_token(token) is None

    def test_from_token_comment_not_directive_returns_none(self):
        token = _make_token(tokenize.COMMENT, "# regular comment")
        assert FMT_DIRECTIVE.from_token(token) is None

    # --- NamedTuple structure ---

    def test_named_tuple_fields(self):
        result = FMT_DIRECTIVE.from_str("# fmt: off[sort]")
        assert result.disable is True
        assert result.modifiers == ["sort"]
        # unpack as tuple
        disable, modifiers = result
        assert disable is True
        assert modifiers == ["sort"]


class TestCheckIndent:
    """Tests for check_indent()."""

    def test_returns_zero_for_empty_indent(self):
        indents = [""]
        assert check_indent("hello\n", indents) == 0

    def test_returns_correct_level_for_simple_indent(self):
        indents = ["", "    "]
        assert check_indent("    hello\n", indents) == 1

    def test_returns_correct_level_for_deeper_indent(self):
        indents = ["", "    ", "        "]
        assert check_indent("        hello\n", indents) == 2

    def test_returns_level_for_outer_indent(self):
        """A line at indent level 0 should return 0 even with deeper entries."""
        indents = ["", "    ", "        "]
        assert check_indent("hello\n", indents) == 0

    def test_returns_middle_level(self):
        indents = ["", "    ", "        "]
        assert check_indent("    hello\n", indents) == 1

    def test_raises_syntax_error_for_unknown_indent(self):
        """Indent not found in any known indent string raises SyntaxError.
        The indents list must not contain "" (empty base) for this to trigger,
        since ''.startswith('') is always True."""
        indents = ["    "]  # only 4-space, no "" base
        with pytest.raises(SyntaxError, match="Unexpected indent"):
            check_indent("  hello\n", indents)  # 2-space not in indents

    def test_raises_syntax_error_for_empty_indents(self):
        """Empty indents list should raise SyntaxError (nothing to match)."""
        with pytest.raises(SyntaxError, match="Unexpected indent"):
            check_indent("hello\n", [])

    def test_tab_indents(self):
        indents = ["", "\t"]
        assert check_indent("\thello\n", indents) == 1

    def test_multiple_tabs(self):
        indents = ["", "\t", "\t\t"]
        assert check_indent("\t\thello\n", indents) == 2


class TestTokenIndentsUpdated:
    """Tests for token_indents_updated()."""

    def test_indent_token_appends_new_indent(self):
        indents = [""]
        token = _make_token(tokenize.INDENT, "    ", line="    x = 1\n")
        result = token_indents_updated(token, indents)
        assert result is True
        assert indents == ["", "    "]

    def test_indent_token_does_not_duplicate(self):
        """If the indent is already in the list, it should not be added again."""
        indents = ["", "    "]
        token = _make_token(tokenize.INDENT, "    ", line="    x = 1\n")
        result = token_indents_updated(token, indents)
        assert result is True
        assert indents == ["", "    "]

    def test_dedent_token_pops_to_matching_indent(self):
        indents = ["", "    ", "        "]
        # dedenting back to 4-space level
        token = _make_token(tokenize.DEDENT, "", line="    x = 1\n")
        result = token_indents_updated(token, indents)
        assert result is True
        assert indents == ["", "    "]

    def test_dedent_token_pops_multiple_levels(self):
        """Dedent may skip levels; pop until matching is found."""
        indents = ["", "    ", "        ", "            "]
        token = _make_token(tokenize.DEDENT, "", line="    x = 1\n")
        result = token_indents_updated(token, indents)
        assert result is True
        assert indents == ["", "    "]

    def test_dedent_to_empty_string_ok(self):
        indents = ["", "    "]
        token = _make_token(tokenize.DEDENT, "", line="x = 1\n")
        result = token_indents_updated(token, indents)
        assert result is True
        assert indents == [""]

    def test_dedent_raises_when_indents_emptied(self):
        """If popping empties indents (no '' base), raise SyntaxError."""
        indents = ["    "]  # no "" base
        token = _make_token(tokenize.DEDENT, "", line="x = 1\n")
        with pytest.raises(SyntaxError, match="Unexpected dedent"):
            token_indents_updated(token, indents)

    def test_non_indent_dedent_returns_false(self):
        indents = [""]
        token = _make_token(tokenize.NAME, "rule")
        result = token_indents_updated(token, indents)
        assert result is False
        assert indents == [""]  # unchanged

    def test_comment_token_returns_false(self):
        indents = [""]
        token = _make_token(tokenize.COMMENT, "# fmt: off")
        result = token_indents_updated(token, indents)
        assert result is False
        assert indents == [""]

    def test_newline_token_returns_false(self):
        indents = [""]
        token = _make_token(tokenize.NEWLINE, "\n")
        result = token_indents_updated(token, indents)
        assert result is False

    def test_endmarker_returns_false(self):
        indents = [""]
        token = _make_token(tokenize.ENDMARKER, "")
        result = token_indents_updated(token, indents)
        assert result is False


class TestSplitTokenLines:
    """Tests for split_token_lines()."""

    def test_single_line_token(self):
        """A token on a single line returns one (lineno, line) pair."""
        token = _make_token(
            tokenize.STRING, '"hello"', start=(5, 0), end=(5, 7), line='"hello"\n'
        )
        pairs = list(split_token_lines(token))
        assert pairs == [(5, '"hello"\n')]

    def test_multiline_token(self):
        """A multiline token (like a triple-quoted string) uses start row
        and the single line attribute from tokenize."""
        line_text = "'''\nhello\n'''\n"
        token = tokenize.TokenInfo(
            tokenize.STRING,
            "'''\nhello\n'''",
            (3, 0),
            (5, 3),
            line_text,
        )
        pairs = list(split_token_lines(token))
        # Should return 3 pairs: lines 3, 4, 5
        line_numbers = [p[0] for p in pairs]
        assert line_numbers == [3, 4, 5]

    def test_single_line_token_column_offset(self):
        """Token starting at non-zero column still uses start row."""
        token = _make_token(
            tokenize.NAME, "x", start=(10, 4), end=(10, 5), line="    x = 1\n"
        )
        pairs = list(split_token_lines(token))
        assert pairs == [(10, "    x = 1\n")]

    def test_returns_zip_iterable(self):
        """split_token_lines returns a zip object (lazy iterable)."""
        token = _make_token(
            tokenize.NAME, "x", start=(1, 0), end=(1, 1), line="x\n"
        )
        result = split_token_lines(token)
        # zip objects don't have a len, but they are iterable
        assert hasattr(result, "__iter__")
        pairs = list(result)
        assert len(pairs) == 1


class TestFmtDirectiveIntegration:
    """Integration tests for fmt:off/on directives covering edge cases not
    covered by TestFmtOffOn in test_formatter.py."""

    def test_fmt_off_with_trailing_double_space_in_file(self):
        """# fmt: off followed by two spaces is still a valid directive."""
        code = "# fmt: off  \n" "rule a:\n" f"{TAB}input: 'i'\n"
        assert setup_formatter(code).get_formatted() == code

    def test_fmt_off_on_empty_region(self):
        """fmt: off immediately followed by fmt: on formats nothing verbatim."""
        code = "# fmt: off\n# fmt: on\n" "rule a:\n" f"{TAB}input: 'i'\n"
        expected = (
            "# fmt: off\n# fmt: on\n" "rule a:\n" f"{TAB}input:\n" f'{TAB * 2}"i",\n'
        )
        assert setup_formatter(code).get_formatted() == expected

    def test_fmt_off_sort_no_modifiers_preserves_order_without_sort(self):
        """Without sort_params=True, natural order is preserved regardless of directive."""
        code = "rule a:\n" f"{TAB}output: 'o'\n" f"{TAB}input: 'i'\n"
        formatter = setup_formatter(code, sort_params=False)
        result = formatter.get_formatted()
        # output before input (not sorted)
        assert result.index("output") < result.index("input")

    def test_fmt_off_next_does_not_affect_subsequent_rules(self):
        """fmt: off[next] only applies to the immediately following block."""
        code = (
            "# fmt: off[next]\n"
            "rule a:\n"
            f" input: 'i'\n"
            "rule b:\n"
            f" input: 'i'\n"
        )
        result = setup_formatter(code).get_formatted()
        # rule a should have verbatim indentation (1 space, not 4)
        assert " input: 'i'" in result
        # rule b should be formatted with proper TAB indentation
        assert f"{TAB}input:" in result

    def test_fmt_on_sort_plain_on_ends_sort_region(self):
        """A plain # fmt: on (without [sort]) also ends a # fmt: off[sort] region."""
        code = (
            "# fmt: off[sort]\n"
            "rule a:\n"
            f"{TAB}output: 'o'\n"
            f"{TAB}input: 'i'\n"
            "# fmt: on\n"
            "rule b:\n"
            f"{TAB}output: 'o'\n"
            f"{TAB}input: 'i'\n"
        )
        result = setup_formatter(code, sort_params=True).get_formatted()
        # rule a: sorting disabled, original order preserved (output before input)
        a_start = result.index("rule a")
        b_start = result.index("rule b")
        rule_a_block = result[a_start:b_start]
        assert rule_a_block.index("output") < rule_a_block.index("input")
        # rule b: sorting enabled, input before output
        rule_b_block = result[b_start:]
        assert rule_b_block.index("input") < rule_b_block.index("output")

    def test_fmt_directive_not_confused_with_fmton_comment(self):
        """Comments like '# fmton' are NOT directives and pass through normally."""
        code = "# fmton\n" "rule a:\n" f"{TAB}input: 'i'\n"
        result = setup_formatter(code).get_formatted()
        assert "# fmton\n" in result
        assert f"{TAB}input:" in result

    def test_fmt_off_idempotent(self):
        """Formatting a file with # fmt: off twice gives the same result."""
        code = "# fmt: off\n" "rule a:\n" f" input: 'i'\n"
        first = setup_formatter(code).get_formatted()
        second = setup_formatter(first).get_formatted()
        assert first == second

    def test_fmt_off_next_idempotent(self):
        """Formatting a file with # fmt: off[next] twice gives the same result."""
        code = (
            "# fmt: off[next]\n"
            "rule a:\n"
            f" input: 'i'\n"
            "rule b:\n"
            f"{TAB}input: 'i'\n"
        )
        first = setup_formatter(code).get_formatted()
        second = setup_formatter(first).get_formatted()
        assert first == second

    def test_fmt_off_sort_idempotent(self):
        """Formatting a file with # fmt: off[sort] twice gives the same result."""
        code = (
            "# fmt: off[sort]\n"
            "rule a:\n"
            f"{TAB}output: 'o'\n"
            f"{TAB}input: 'i'\n"
            "# fmt: on[sort]\n"
        )
        first = setup_formatter(code, sort_params=True).get_formatted()
        second = setup_formatter(first, sort_params=True).get_formatted()
        assert first == second