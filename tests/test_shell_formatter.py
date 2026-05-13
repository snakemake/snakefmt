import pytest

from snakefmt.exceptions import InvalidShell
from snakefmt.shell_formatter import format_python_string_literal, format_shell_code

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
