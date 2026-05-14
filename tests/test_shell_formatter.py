import pytest

from snakefmt.exceptions import InvalidShell
from snakefmt.shell_formatter import (
    _indent_preserving_heredocs,
    format_python_string_literal,
    format_shell_code,
)

# Shell content that shfmt will reformat (not already at fixed-point).
# Input: un-indented if/then/fi without semicolon-compression.
# Output: shfmt normalises to `if ...; then` form with 4-space body indent.
_UNFORMATTED_CONTENT = "if [ -s /tmp/out ]\nthen\necho done\nfi"
_EXPECTED_CONTENT = "if [ -s /tmp/out ]; then\n    echo done\nfi\n"
_EXPECTED_LITERAL = f'"""\n{_EXPECTED_CONTENT}"""'


def test_format_python_string_literal():
    literal = 'f"""\n      echo {input}\n    ls -l\n    """'
    expected = 'f"""\n        echo {input}\n        ls -l\n        """'
    assert format_python_string_literal(literal, target_indent=2) == expected


@pytest.mark.parametrize(
    "literal,expected",
    [
        # 1. Trailing \n after closing quotes — the actual parser-output bug.
        (
            f'"""\n{_UNFORMATTED_CONTENT}\n"""\n',
            _EXPECTED_LITERAL,
        ),
        # 2. Multiple trailing newlines.
        (
            f'"""\n{_UNFORMATTED_CONTENT}\n"""\n\n',
            _EXPECTED_LITERAL,
        ),
        # 3. Trailing spaces / tabs after closing quotes.
        (
            f'"""\n{_UNFORMATTED_CONTENT}\n"""   \t',
            _EXPECTED_LITERAL,
        ),
        # 4. \r\n line endings inside — shfmt normalises to \n in output.
        (
            '"""\r\n' + _UNFORMATTED_CONTENT.replace("\n", "\r\n") + '\r\n"""',
            _EXPECTED_LITERAL,
        ),
        # 5. String prefix variants — prefix must be preserved, content formatted.
        (f'f"""\n{_UNFORMATTED_CONTENT}\n"""\n', f'f"""\n{_EXPECTED_CONTENT}"""'),
        (f'rb"""\n{_UNFORMATTED_CONTENT}\n"""\n', f'rb"""\n{_EXPECTED_CONTENT}"""'),
        (f'B"""\n{_UNFORMATTED_CONTENT}\n"""\n', f'B"""\n{_EXPECTED_CONTENT}"""'),
        (f'u"""\n{_UNFORMATTED_CONTENT}\n"""\n', f'u"""\n{_EXPECTED_CONTENT}"""'),
    ],
    ids=[
        "trailing_newline",
        "multiple_trailing_newlines",
        "trailing_spaces_tabs",
        "crlf_line_endings",
        "prefix_f",
        "prefix_rb",
        "prefix_B",
        "prefix_u",
    ],
)
def test_format_python_string_literal_trailing_whitespace_shapes(literal, expected):
    """format_python_string_literal must format content regardless of trailing
    whitespace after the closing quotes — the form produced by the parser."""
    assert format_python_string_literal(literal, target_indent=0) == expected


def test_format_shell_code_simple():
    unformatted = """
        echo "hello"
          ls -l
    """
    expected = """\
echo "hello"
ls -l
"""
    assert format_shell_code(unformatted) == expected


def test_format_shell_code_with_variables():
    unformatted = """
        echo {input.foo} > {output[0]}
        for f in {input}; do
            cat $f
        done
    """
    expected = """\
echo {input.foo} >{output[0]}
for f in {input}; do
    cat $f
done
"""
    assert format_shell_code(unformatted) == expected


def test_format_shell_code_escaped_braces():
    unformatted = """
        awk '{{print $1}}' {input}
    """
    expected = """\
awk '{{print $1}}' {input}
"""
    assert format_shell_code(unformatted) == expected


def test_format_shell_code_many_variables():
    # Tests that __SNAKEFMT_VAR_1__ doesn't accidentally replace __SNAKEFMT_VAR_10__
    vars = [f"{{var{i}}}" for i in range(15)]
    unformatted = "echo " + " ".join(vars) + "\n"
    expected = "echo " + " ".join(vars) + "\n"
    assert format_shell_code(unformatted) == expected


def test_format_shell_code_invalid_syntax():
    unformatted = """
        if [ -z "foo" ]; then
            echo "bar"
    """
    with pytest.raises(InvalidShell):
        format_shell_code(unformatted)


def test_format_shell_code_double_brace_param_expansion():
    # ${{VAR}} in Snakemake source → ${VAR} in shell → must round-trip verbatim.
    code = "echo ${{VAR}} ${{VAR:-default}}\n"
    assert format_shell_code(code) == code


def test_format_shell_code_double_brace_expansion():
    # {{a,b,c}} → {a,b,c} brace expansion in shell.
    code = "cp f{{1,2}}.txt output/\n"
    assert format_shell_code(code) == code


def test_format_shell_code_brace_group_preserved():
    # Brace group {{ echo hi; echo bye; }} is masked verbatim — body not internally
    # reformatted (accepted trade-off: brace count must survive str.format()).
    code = "{{ echo hi; echo bye; }}\n"
    assert format_shell_code(code) == code


def test_format_shell_code_awk_double_braces():
    # awk '{{print $1}}' — already tested but confirm it still works after C1.
    code = "awk '{{print $1}}' {input}\n"
    assert format_shell_code(code) == code


def test_format_shell_code_awk_double_braces_with_inner_var():
    # {{...}} containing a single {var} must be preserved and not mangled by shfmt.
    code = "awk '{{print {params.a} }}'\n"
    assert format_shell_code(code) == code


def test_format_shell_code_unquoted_double_braces_with_inner_var():
    # Unquoted {{...}} containing a variable must be masked entirely by the double
    # brace pass so that shfmt doesn't reformat the inside as nested brace groups.
    code = "{{\n    echo {params.a}\n}}\n"
    assert format_shell_code(code) == code


def test_format_python_string_literal_fstring_formatted():
    # F-string shell blocks must be formatted, not skipped.
    # {{output}} is a Snakemake variable in f-string context (Python collapses
    # {{}} → {}, then Snakemake substitutes). It must round-trip verbatim.
    literal = 'f"""\necho {{output}}\nls -l\n"""'
    result = format_python_string_literal(literal, target_indent=0)
    assert "{{output}}" in result
    assert result.startswith('f"""')


def test_format_shell_code_long_line_no_spurious_wrap():
    # shfmt with -i 4 -ci -bn is syntactic only — no length-based line wrapping.
    # Mask tokens (~50 chars each) must not cause spurious line breaks post-unmask.
    vars_str = " ".join(f"{{var{i}}}" for i in range(10))
    unformatted = f"echo {vars_str}\n"
    assert format_shell_code(unformatted) == unformatted


class TestIndentPreservingHeredocs:
    def test_plain_lines_indented(self):
        text = "echo hello\necho world\n"
        result = _indent_preserving_heredocs(text, "    ")
        assert result == "    echo hello\n    echo world\n"

    def test_blank_lines_not_indented(self):
        text = "echo hi\n\necho bye\n"
        result = _indent_preserving_heredocs(text, "    ")
        assert result == "    echo hi\n\n    echo bye\n"

    def test_heredoc_body_and_terminator_not_indented(self):
        text = "cat <<EOF\nbody line\nEOF\n"
        result = _indent_preserving_heredocs(text, "    ")
        assert result == "    cat <<EOF\nbody line\nEOF\n"

    def test_heredoc_dash_terminator_with_leading_tabs(self):
        # <<-EOF: terminator may have leading tabs — still recognised as terminator.
        text = "cat <<-EOF\n\tbody line\n\tEOF\n"
        result = _indent_preserving_heredocs(text, "    ")
        assert result == "    cat <<-EOF\n\tbody line\n\tEOF\n"

    def test_heredoc_quoted_terminator(self):
        # <<'EOF' suppresses substitution in the body but terminator is same word.
        text = "cat <<'EOF'\nbody line\nEOF\n"
        result = _indent_preserving_heredocs(text, "    ")
        assert result == "    cat <<'EOF'\nbody line\nEOF\n"

    def test_multiple_commands_after_heredoc(self):
        text = "cat <<EOF\nbody\nEOF\necho done\n"
        result = _indent_preserving_heredocs(text, "    ")
        assert result == "    cat <<EOF\nbody\nEOF\n    echo done\n"


class TestFormatPythonStringLiteralHeredocs:
    def test_heredoc_terminator_at_column_zero(self):
        # <<EOF: terminator must remain at column 0 after snakefmt indentation.
        # The user writes the heredoc with the terminator at col 0 in the source.
        literal = '"""\ncat <<EOF\nsome content\nEOF\n"""'
        result = format_python_string_literal(literal, target_indent=2)
        # Command is indented; body and terminator are NOT.
        assert "        cat <<EOF\n" in result
        assert "\nsome content\n" in result
        assert "\nEOF\n" in result
        # Terminator must not be preceded by spaces on its line.
        for line in result.splitlines():
            if line.strip() == "EOF":
                assert line == "EOF", f"Terminator line is indented: {line!r}"

    def test_heredoc_with_snakemake_variable_in_command(self):
        # Snakemake {output} in the command line of a heredoc — must survive.
        literal = '"""\ncat <<EOF >{output}\nsome content\nEOF\n"""'
        result = format_python_string_literal(literal, target_indent=2)
        assert "{output}" in result
        assert "EOF\n" in result

    def test_heredoc_with_custom_delimiter_and_newlines(self):
        # Simulates a Python multi-line string containing a heredoc
        literal = '"""\npython <<!EOF!\n\\nif True:\n\npass\n\n\\n\n!EOF!\n"""'
        expected = '"""\n        python <<!EOF!\n\\nif True:\n\npass\n\n\\n\n!EOF!\n        """'
        assert format_python_string_literal(literal, target_indent=2) == expected
