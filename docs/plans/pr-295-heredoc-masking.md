# PR #295: Heredoc body masking

**PR:** [#295](https://github.com/snakemake/snakefmt/pull/295) — `feat!: format shell directives using shfmt`
**Reviewer:** Hocnonsense, review `4294612620` on 2026-05-15
**Status:** Plan drafted 2026-05-15

## Problem

The reviewer ran `snakefmt` on a real snakefile and hit:

```
snakefmt.exceptions.InvalidShell: Invalid shell code. shfmt error:
<standard input>:18:16: unclosed here-document `!EOF!`
```

The offending shell block (excerpt):

```
shell:
    """
    ...
    python <<!EOF!
    \nif True:
    ...
    norm.to_csv(outfile, sep="\t")

    \n!EOF!
    """
```

The terminator line is `\n!EOF!`, not `!EOF!`. shfmt requires the terminator
word to appear on its own line (column 0 for `<<DELIM`, leading tabs only for
`<<-DELIM`). It doesn't match `\n!EOF!`, so shfmt declares the heredoc unclosed
and aborts. snakefmt propagates this as `InvalidShell` and the entire file
fails to format.

The user's workaround today is `# fmt: off` around every shell block that uses
this pattern — too brittle for real-world Snakemake codebases.

The reviewer's other findings:

- **Finding 2 — docstring indentation in non-shell directives.** Reviewer
  marked out of scope. Confirmed: this is Black v26 docstring normalisation,
  not anything our shfmt path touches. Defer.
- **Finding 3 — "code should be formatted to run full tests".** Re-statement
  of Finding 1 from a UX angle. Subsumed by the heredoc fix.

## Why graceful degradation is the wrong fix

The first instinct is "catch `InvalidShell`, log a warning, leave the block
alone." This is what the reviewer was effectively doing manually with
`# fmt: off`. It avoids the crash but doesn't help the user — their shell
block still gets no formatting, and they still need to discover which blocks
are problematic.

The user explicitly pushed back on this: "I don't want to just throw up my
hands and say, too hard!" — fix the actual case.

## Root cause + fix

### Key observation

shfmt **does not reformat heredoc body content.** We already rely on this in
`_indent_preserving_heredocs`, which only re-indents non-heredoc lines. So
shfmt does not need to see the real heredoc body to do its job — it only
needs to be able to *parse around it*.

### Fix

Pre-process the masked code, before shfmt runs: for each heredoc, detect the
user-intended terminator (permissively, accepting snakemake-style escape
prefixes like `\n!EOF!`) and replace the body + terminator with a
placeholder body line + a clean terminator. shfmt parses happily, formats
the surrounding code, and returns. After shfmt returns, splice the original
body + terminator back in.

```python
# Updated pipeline:
def format_shell_code(code: str) -> str:
    masked, var_tokens, var_originals = _mask_snakemake_vars(code)
    masked, heredoc_blocks = _mask_heredocs(masked)         # NEW
    formatted = _invoke_shfmt(masked)
    formatted = _unmask_heredocs(formatted, heredoc_blocks) # NEW
    return _unmask_snakemake_vars(formatted, var_tokens, var_originals)
```

`_indent_preserving_heredocs` (called downstream by
`format_python_string_literal`) is unchanged — it continues to handle
post-shfmt indentation correctly.

### Terminator-detection heuristic

Walk forward from `<<DELIM`. The terminator is the **first** subsequent line
where:

1. The line ends with `DELIM` (followed only by optional trailing whitespace).
2. Everything before `DELIM` on that line matches `^[\s]*(\\[a-z])*$` — i.e.,
   the prefix consists only of whitespace, tabs, and backslash-escape
   sequences like `\n`, `\t`.

```python
# Pseudocode
def _looks_like_terminator(line: str, delim: str) -> bool:
    stripped = line.rstrip()
    if not stripped.endswith(delim):
        return False
    prefix = stripped[: -len(delim)]
    return re.fullmatch(r"[\s]*(\\[a-z])*", prefix) is not None
```

Cases this catches (✓) vs ignores (✗):

| Body line | Terminator? | Why |
|-----------|-------------|-----|
| `EOF` | ✓ | Standard |
| `\tEOF` | ✓ | `<<-EOF` form |
| `    EOF` | ✓ | Leading whitespace before our re-indent runs |
| `\n!EOF!` | ✓ | Snakemake escape prefix |
| `\n\n!EOF!` | ✓ | Multiple escapes |
| `prefix_EOF` | ✗ | DELIM not preceded by whitespace/escape |
| `EOF more text` | ✗ | DELIM not at end of line |
| `# EOF` | ✗ | `#` is not a recognised escape prefix |

### Mask + restore mechanics

```python
_HEREDOC_TOKEN_FMT = "__SNAKEFMT_HEREDOC_{nonce}_{idx}__"

def _mask_heredocs(code: str) -> tuple[str, tuple[tuple[str, str], ...]]:
    """Replace heredoc body+terminator with a placeholder body + clean terminator
    line so shfmt can parse the surrounding shell.

    Returns (masked_code, blocks) where blocks[i] is (token, original_block_text).
    """
    nonce = uuid.uuid4().hex
    out_lines: list[str] = []
    blocks: list[tuple[str, str]] = []
    lines = code.splitlines(keepends=True)

    i = 0
    while i < len(lines):
        line = lines[i]
        m = _HEREDOC_START.search(line)
        if not m:
            out_lines.append(line)
            i += 1
            continue

        delim = m.group(1)
        out_lines.append(line)  # keep the <<DELIM command line
        i += 1

        # Walk forward for the terminator.
        body_start = i
        terminator_idx: int | None = None
        while i < len(lines):
            if _looks_like_terminator(lines[i], delim):
                terminator_idx = i
                break
            i += 1

        if terminator_idx is None:
            # No terminator found — leave the rest as-is; shfmt will error
            # with the genuine "unclosed here-document" message.
            out_lines.extend(lines[body_start:])
            return "".join(out_lines), tuple(blocks)

        original_block = "".join(lines[body_start : terminator_idx + 1])
        token = _HEREDOC_TOKEN_FMT.format(nonce=nonce, idx=len(blocks))
        blocks.append((token, original_block))

        # Insert: placeholder body line containing the token, then a clean
        # terminator at column 0.
        out_lines.append(token + "\n")
        out_lines.append(delim + "\n")
        i = terminator_idx + 1

    return "".join(out_lines), tuple(blocks)


def _unmask_heredocs(code: str, blocks: tuple[tuple[str, str], ...]) -> str:
    """Restore heredoc bodies + terminators, undoing _mask_heredocs."""
    for token, original in blocks:
        # Replace the token line + the next line (clean terminator) with
        # the original body+terminator block.
        marker = re.compile(re.escape(token) + r".*\n.*\n", re.DOTALL)
        code = marker.sub(lambda _m: original, code, count=1)
    return code
```

UUID nonce + indexed token guarantees uniqueness across calls and immunity
from collision with literal user content (same pattern as
`_mask_snakemake_vars`).

## Cases the fix handles

1. **The reviewer's exact case** — `python <<!EOF!` with `\n!EOF!` terminator
   → masked, formatted, restored verbatim.
2. **Standard heredocs** (`<<EOF`, `<<-EOF`, `<<'EOF'`) — terminator detected,
   body preserved, behaviour identical to today.
3. **Multiple heredocs in one shell block** — each masked independently with
   distinct token indices; restored in order.
4. **Heredoc body that looks like reformattable shell** — body never touched
   by shfmt because shfmt sees only the placeholder.
5. **Surrounding shell still gets formatted** — masking only the body +
   terminator, not the `<<DELIM` line, leaves shfmt free to reformat the
   pipeline around the heredoc.

## Cases NOT handled (intentional)

1. **Truly unclosed heredoc** (no terminator-like line anywhere in the rest
   of the block) — `_mask_heredocs` falls through, shfmt receives the
   original input, raises `InvalidShell` as before. This is genuine bash
   error, not snakefmt's job to paper over.
2. **DELIM appearing as substring inside legitimate body content with
   whitespace prefix** (e.g., body line ` EOF ` where the user *meant* it as
   data, not a terminator) — heuristic will detect it as the terminator.
   Vanishingly rare in real heredocs; documented as a known limitation.

## Tests to add

In `tests/test_shell_formatter.py`:

```python
def test_format_shell_code_heredoc_with_snakemake_escape_terminator():
    """Reviewer's exact case: \\n!EOF! is detected as the user-intended
    terminator and masked, even though shfmt alone would fail on it."""
    code = (
        "python <<!EOF!\n"
        "\\nif True:\n"
        "    pass\n"
        "\n"
        "\\n!EOF!\n"
    )
    # Round-trips verbatim — body and terminator restored exactly.
    assert format_shell_code(code) == code


def test_format_shell_code_heredoc_body_never_reformatted():
    """Body content that looks like reformattable shell stays untouched."""
    code = (
        "cat <<EOF\n"
        "if true\nthen\necho yes\nfi\n"  # NOT formatted by shfmt
        "EOF\n"
    )
    assert format_shell_code(code) == code


def test_format_shell_code_multiple_heredocs():
    """Two heredocs in the same block round-trip independently."""
    code = (
        "cat <<EOF\nbody1\nEOF\n"
        "cat <<END\nbody2\nEND\n"
    )
    assert format_shell_code(code) == code


def test_format_shell_code_heredoc_surrounded_by_formatted_shell():
    """Shell around the heredoc gets formatted; heredoc body stays verbatim."""
    unformatted = (
        "if true\nthen\n"
        "cat <<EOF\nbody\nEOF\n"
        "fi\n"
    )
    expected = (
        "if true; then\n"
        "    cat <<EOF\nbody\nEOF\n"
        "fi\n"
    )
    assert format_shell_code(unformatted) == expected


def test_format_shell_code_truly_unclosed_heredoc_raises():
    """No terminator candidate → shfmt sees the original, raises InvalidShell."""
    code = "cat <<EOF\nbody with no terminator anywhere\n"
    with pytest.raises(InvalidShell):
        format_shell_code(code)
```

Existing tests in `TestIndentPreservingHeredocs` and
`TestFormatPythonStringLiteralHeredocs` continue to pass — `_mask_heredocs`
runs upstream of `_indent_preserving_heredocs` and doesn't change its
contract.

## README addendum

Update the "Snakemake placeholders" / "Invalid shell" subsection of the
shell-formatting section: snakefmt now masks heredoc bodies before invoking
shfmt, so heredocs that use snakemake-style escape prefixes on their
terminator (e.g., `\n!EOF!`) format successfully without `# fmt: off`.
Heredoc body content is never reformatted (matches shfmt's own behaviour).

## Execution order

1. Add `_HEREDOC_TOKEN_FMT`, `_looks_like_terminator`, `_mask_heredocs`,
   `_unmask_heredocs` to `snakefmt/shell_formatter.py`.
2. Wire them into `format_shell_code`.
3. Add the five new tests in `tests/test_shell_formatter.py`.
4. Run snakefmt against the reviewer's exact snakefile snippet (smoke test)
   — verify it formats without `# fmt: off`.
5. Update README "Invalid shell" subsection.
6. Validate: `make fmt && make lint && uv run pytest -q`.
7. Commit (one focused commit) + push.

## Out of scope

- **Finding 2 (docstring indentation in non-shell rules)** — Black v26
  behaviour, not snakefmt; reviewer marked out of scope.
- **Graceful degradation fallback** — explicitly rejected by the user; we
  fix the actual case rather than mask the symptom.
- **CLI flag for strict-vs-warn behaviour** — not needed; the fix is
  transparent.
