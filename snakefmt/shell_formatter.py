import re
import subprocess
import textwrap
import uuid

from snakefmt.exceptions import InvalidShell

TAB = "    "

# Matches `{var}` while ignoring escaped `{{...}}` braces (which Snakemake
# passes through to the shell verbatim, e.g. `awk '{{print $1}}'`).
# The leading character class avoids matching shell function bodies like
# `foo() { echo bar }`.
# Intentionally permissive beyond the first character: in Snakemake shell
# blocks, ALL single {…} are Snakemake expressions by definition — literal
# braces must use {{…}}. This correctly captures {input[0]}, {threads:02d},
# {wildcards.sample}, etc.
_SNAKEMAKE_VAR_PATTERN = re.compile(r"(?<!\{)\{([a-zA-Z0-9_][^{}]*)\}(?!\})")


def _mask_snakemake_vars(code: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Replace Snakemake `{var}` placeholders with opaque tokens shfmt won't touch.

    Uses a per-call UUID nonce in the token to eliminate any risk of collision
    with literal text that happens to look like a mask token.

    Returns (masked_code, tokens, originals) — tokens[i] is the exact string
    inserted for originals[i], so _unmask_snakemake_vars can replace by value
    rather than by reconstructing the template.
    """
    nonce = uuid.uuid4().hex
    tokens: list[str] = []
    originals: list[str] = []

    def replace(match: re.Match[str]) -> str:
        token = f"__SNAKEFMT_{nonce}_{len(tokens)}__"
        tokens.append(token)
        originals.append(match.group(0))
        return token

    masked = _SNAKEMAKE_VAR_PATTERN.sub(replace, code)
    return masked, tuple(tokens), tuple(originals)


def _unmask_snakemake_vars(
    code: str, tokens: tuple[str, ...], originals: tuple[str, ...]
) -> str:
    """Reverse of `_mask_snakemake_vars`. Replaces each token by its stored
    string value rather than re-constructing from a template."""
    for token, original in zip(reversed(tokens), reversed(originals)):
        code = code.replace(token, original)
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
    masked, tokens, originals = _mask_snakemake_vars(code)
    formatted = _invoke_shfmt(masked)
    return _unmask_snakemake_vars(formatted, tokens, originals)


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
