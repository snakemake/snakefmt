import re
import subprocess
import textwrap

from snakefmt.exceptions import InvalidShell

TAB = "    "

# Matches `{var}` while ignoring escaped `{{...}}` braces (which Snakemake
# passes through to the shell verbatim, e.g. `awk '{{print $1}}'`).
# The leading character class avoids matching shell function bodies like
# `foo() { echo bar }`.
_SNAKEMAKE_VAR_PATTERN = re.compile(r"(?<!\{)\{([a-zA-Z0-9_][^{}]*)\}(?!\})")

_MASK_TEMPLATE = "__SNAKEFMT_VAR_{}__"


def _mask_snakemake_vars(code: str) -> tuple[str, tuple[str, ...]]:
    """Replace Snakemake `{var}` placeholders with opaque tokens shfmt won't touch."""
    originals: list[str] = []

    def replace(match: re.Match[str]) -> str:
        originals.append(match.group(0))
        return _MASK_TEMPLATE.format(len(originals) - 1)

    masked = _SNAKEMAKE_VAR_PATTERN.sub(replace, code)
    return masked, tuple(originals)


def _unmask_snakemake_vars(code: str, originals: tuple[str, ...]) -> str:
    """Reverse of `_mask_snakemake_vars`. Walks tokens in reverse to avoid
    substring collisions between e.g. `__SNAKEFMT_VAR_1__` and `__SNAKEFMT_VAR_10__`."""
    for i in range(len(originals) - 1, -1, -1):
        code = code.replace(_MASK_TEMPLATE.format(i), originals[i])
    return code


def _invoke_shfmt(code: str) -> str:
    """Run the bundled shfmt binary against `code`. Seam for future swaps —
    see docs/adr/0001-shell-formatter-distribution.md."""
    try:
        process = subprocess.run(
            ["shfmt", "-i", "4", "-ci", "-bn"],
            input=code,
            text=True,
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise InvalidShell(f"Invalid shell code. shfmt error: {e.stderr}")
    return process.stdout


def format_shell_code(code: str) -> str:
    """Format shell code using shfmt, preserving Snakemake `{var}` placeholders."""
    masked, originals = _mask_snakemake_vars(code)
    formatted = _invoke_shfmt(masked)
    return _unmask_snakemake_vars(formatted, originals)


def format_python_string_literal(literal: str, target_indent: int = 0) -> str:
    """Extracts shell code from a Python string literal, formats it, and re-wraps it."""
    # We only format multiline strings for safety, as single line strings
    # might just be a single command or not worth formatting.
    # This also avoids issues with implicitly concatenated strings.
    # Strip trailing whitespace: the parser appends a NEWLINE token after the
    # closing triple-quote, so the literal arrives as '"""..."""\n'. The caller
    # already rstrips the result, so this is safe.
    literal = literal.rstrip()
    match = re.fullmatch(r'^([a-zA-Z]*)(""")([\s\S]*?)(\2)$', literal)
    if not match:
        match = re.fullmatch(r"^([a-zA-Z]*)(''')([\s\S]*?)(\2)$", literal)

    if not match:
        return literal  # Not a simple multiline string literal, don't format

    prefix = match.group(1)
    quote = match.group(2)
    content = match.group(3)

    formatted_content = format_shell_code(content)

    # Ensure it ends with a single newline before the closing quotes
    formatted_content = formatted_content.rstrip("\n") + "\n"

    # Indent the content
    used_indent = TAB * target_indent
    indented_content = textwrap.indent(formatted_content, used_indent)

    # Prepend a newline if the first line is indented so it drops below opening quote
    if indented_content and not indented_content.startswith("\n"):
        indented_content = "\n" + indented_content

    # Indent the closing quote
    closing_quote = f"{used_indent}{quote}"

    return f"{prefix}{quote}{indented_content}{closing_quote}"
