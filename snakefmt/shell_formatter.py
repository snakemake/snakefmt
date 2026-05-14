import re
import subprocess
import uuid

from snakefmt.exceptions import InvalidShell

TAB = "    "

# Matches `{{...}}` escaped brace pairs — these encode literal shell `{...}` after
# Snakemake's str.format() render. Masked FIRST so the single-brace pattern doesn't
# partially match their inner content. Pattern: any content without nested braces.
_DOUBLE_BRACE_PATTERN = re.compile(r"\{\{.*?\}\}", flags=re.DOTALL)

# Matches single `{var}` Snakemake placeholders. The leading character class avoids
# matching shell function bodies like `foo() { echo bar }`. The negative
# lookahead/lookbehind guards against `{{...}}` which was already masked above.
# Intentionally permissive beyond the first character: captures {input[0]},
# {threads:02d}, {wildcards.sample}, etc.
_SINGLE_BRACE_PATTERN = re.compile(r"(?<!\{)\{([a-zA-Z0-9_][^{}]*)\}(?!\})")


def _mask_snakemake_vars(code: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Replace Snakemake placeholders and escaped brace pairs with opaque tokens.

    Masks in two passes: `{{...}}` first, then single `{var}` placeholders. This
    ordering prevents the single-brace pattern from matching inside double-brace
    content and ensures both forms survive shfmt unchanged.

    Uses a per-call UUID nonce in each token to eliminate any risk of collision
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

    code = _DOUBLE_BRACE_PATTERN.sub(replace, code)
    code = _SINGLE_BRACE_PATTERN.sub(replace, code)
    return code, tuple(tokens), tuple(originals)


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
        raise InvalidShell(f"Invalid shell code. shfmt error: {e.stderr}") from e
    return process.stdout


def format_shell_code(code: str) -> str:
    """Format shell code using shfmt, preserving Snakemake `{var}` placeholders."""
    masked, tokens, originals = _mask_snakemake_vars(code)
    formatted = _invoke_shfmt(masked)
    return _unmask_snakemake_vars(formatted, tokens, originals)


_HEREDOC_START = re.compile(r"<<-?\s*['\"]?([^'\"\s<>|;&()]+)['\"]?")

# Matches any Python triple-quoted string literal, with or without a prefix (f, r, b,
# etc.). Uses `"{3}|'{3}` so the closing backreference \2 matches the same quote style
# without needing backslash escapes that confuse formatters inside raw strings.
_TRIPLE_QUOTE_RE = re.compile(r"""^([a-zA-Z]*)("{3}|'{3})([\s\S]*?)(\2)$""")


def _indent_preserving_heredocs(text: str, indent: str) -> str:
    """Indent each line by `indent`, skipping heredoc body and terminator lines.

    shfmt does not reformat heredoc bodies. This function mirrors that — it adds
    the target indent to command lines but leaves heredoc content untouched so that
    terminator words remain at column 0 (required by bash for `<<EOF`) or with only
    leading tabs (for `<<-EOF`).
    """
    out_lines: list[str] = []
    in_heredoc: str | None = None
    for line in text.splitlines(keepends=True):
        stripped = line.rstrip("\n")
        if in_heredoc is not None:
            out_lines.append(line)
            if stripped == in_heredoc or stripped.lstrip("\t") == in_heredoc:
                in_heredoc = None
            continue
        out_lines.append(indent + line if line.strip() else line)
        m = _HEREDOC_START.search(line)
        if m:
            in_heredoc = m.group(1)
    return "".join(out_lines)


def format_python_string_literal(literal: str, target_indent: int = 0) -> str:
    """Extracts shell code from a Python string literal, formats it, and re-wraps it.

    Only multiline triple-quoted strings are formatted. Single-line strings and any
    form that doesn't match a simple triple-quote pattern are returned unchanged.
    The literal is expected to arrive from `str(parameter)` — the caller guarantees
    no leading whitespace beyond what the parser appends (handled by `rstrip` below).
    """
    # Strip trailing whitespace: the parser appends a NEWLINE token after the
    # closing triple-quote, so the literal arrives as '"""..."""\n'. The caller
    # already rstrips the result, so this is safe.
    literal = literal.rstrip()
    match = _TRIPLE_QUOTE_RE.fullmatch(literal)

    if not match:
        return literal  # not a triple-quoted string literal; return unchanged

    prefix = match.group(1)
    quote = match.group(2)
    content = match.group(3)

    formatted_content = format_shell_code(content)

    # Ensure it ends with a single newline before the closing quotes
    formatted_content = formatted_content.rstrip("\n") + "\n"

    # Indent the content, preserving heredoc terminator placement
    used_indent = TAB * target_indent
    indented_content = _indent_preserving_heredocs(formatted_content, used_indent)

    # Prepend a newline if the first line is indented so it drops below opening quote
    if indented_content and not indented_content.startswith("\n"):
        indented_content = "\n" + indented_content

    # Indent the closing quote
    closing_quote = f"{used_indent}{quote}"

    return f"{prefix}{quote}{indented_content}{closing_quote}"
