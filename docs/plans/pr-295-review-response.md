# PR #295 Review Response Plan

**PR:** [#295](https://github.com/snakemake/snakefmt/pull/295) — `feat!: format shell directives using shfmt`
**Reviewers:** Hocnonsense (CHANGES_REQUESTED), CodeRabbit (auto)
**Status:** Plan drafted 2026-05-14

## Reviewer Findings

### Already addressed (CodeRabbit)

- **Mask token UUID nonce** — fixed in commit `f261ae3`. Per-call nonce eliminates collision risk between mask tokens and literal user text.
- **Pattern tightening** (`{...}` regex too permissive) — declined. Tightening to disallow `[`, `:`, `.` would break valid Snakemake syntax like `{input[0]}`, `{threads:02d}`, `{wildcards.sample}`. The negative lookahead/lookbehind (`(?<!\{)`, `(?!\})`) plus the leading character class `[a-zA-Z0-9_]` give sufficient guard against shell function bodies (`fn() { … }`) since those don't start with an identifier character immediately after `{`.

### To fix in this PR

#### B2 — Heredoc indentation breakage (correctness, blocker)

**Source:** Hocnonsense, `snakefmt/shell_formatter.py:105`.

`textwrap.indent` prepends `used_indent` to **every line** of the shfmt output. This corrupts heredocs:

- `<<EOF` requires the terminator at column 0 → after indent, bash never closes the heredoc.
- `<<-EOF` strips only leading **tabs**, not spaces → space-indent still breaks the terminator.
- Body content inside the heredoc (e.g. embedded Python) has semantically-significant indentation that uniform space-padding corrupts.

**Fix:** heredoc-aware indent. After shfmt produces output, parse for heredoc start markers and skip indenting body + terminator lines.

```python
_HEREDOC_START = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")

def _indent_preserving_heredocs(text: str, indent: str) -> str:
    """Indent each line by `indent` except inside heredoc bodies, where the
    terminator must remain at column 0 (or leading tabs only for <<-)."""
    out_lines: list[str] = []
    in_heredoc: str | None = None  # terminator word when inside
    for line in text.splitlines(keepends=True):
        stripped_for_term = line.rstrip("\n")
        if in_heredoc is not None:
            out_lines.append(line)  # never indent body lines
            if stripped_for_term == in_heredoc or stripped_for_term.lstrip("\t") == in_heredoc:
                in_heredoc = None
            continue
        out_lines.append(indent + line if line.strip() else line)
        m = _HEREDOC_START.search(line)
        if m:
            in_heredoc = m.group(1)
    return "".join(out_lines)
```

Replaces the single `textwrap.indent(formatted_content, used_indent)` call.

shfmt is already heredoc-aware: it does not reformat heredoc bodies. So the only contribution snakefmt needs to make is to not destroy them on the way out.

**Edge cases to handle:**
- Quoted terminator: `<<'EOF'` and `<<"EOF"` — same terminator word, just no shell-expansion in body.
- `<<-EOF` (dash) — terminator may have leading tabs.
- Multiple heredocs on one line (rare but legal): `cmd <<EOF1 <<EOF2`. Punt on this; document as known limitation.
- Quoted text containing `<<word` inside `'...'` or `"..."` — must not trigger heredoc mode. The simple regex above will misfire; either accept this as a rare case or use a more careful tokenizer. **Decision:** accept for v1, add a test that documents the false-positive corner case.

#### C1 — Mask `{{...}}` to preserve brace count and Snakemake/bash semantics (correctness, blocker)

**Source:** Hocnonsense comments #3, #6, #8b.

**Problem:** `{{...}}` in source must round-trip verbatim through shfmt because:

1. **Snakemake `str.format()` brace counting:** Snakemake renders shell strings via `str.format()`, which only accepts `{{` → `{` and `}}` → `}` as escape pairs. If shfmt ever splits `{{` into `{ {` while wrapping (e.g. when reformatting a brace group), post-render raises `ValueError: Single '{' encountered in format string`.
2. **Plain-string brace expansion** (#8b): `cp tmp/{{a,b}} output/` represents `cp tmp/{a,b} output/` to the shell. shfmt formatting `{{a,b}}` directly may differ from how it would format `{a,b}`.
3. **F-string Snakemake variables** (#3, #6): In an f-string, `{{output}}` is the actual Snakemake variable (Python collapses `{{}}` → `{}`, then Snakemake substitutes). Currently NOT masked, so shfmt sees `{{output}}` literally and may reformat in ways that break post-Python brace counting.

**Decision: mask all `{{...}}` patterns** uniformly across plain strings and f-strings. The formatter does not need to model runtime semantics — it preserves every brace-bracketed token verbatim.

**Trade-off (accepted):** bash brace groups `{{ cmd1; cmd2; }}` lose internal formatting because shfmt sees only an opaque token. This case is rare in Snakemake shell directives (`&&` chains and line continuations cover most pipelines). Users who need brace-group formatting can use `# fmt: off`.

**Cases preserved correctly under this policy:**

| Case | Source | Bash sees | Round-trip |
|------|--------|-----------|------------|
| Brace group | `{{ echo hi; }}` | `{ echo hi; }` | ✓ verbatim, no internal formatting |
| Parameter expansion | `${{VAR}}` | `${VAR}` | ✓ shfmt sees `$TOKEN`, restored to `${{VAR}}` |
| Brace expansion | `cp f{{1,2}}.txt` | `cp f{1,2}.txt` | ✓ token preserved |
| awk/sed in quotes | `awk '{{print $1}}'` | `awk '{print $1}'` | ✓ no-op (shfmt doesn't reformat quoted content) |
| F-string Snakemake var | `f"echo {{output}}"` | substituted path | ✓ token preserved |

Implementation outline:

```python
_DOUBLE_BRACE_PATTERN = re.compile(r"\{\{[^{}]*\}\}")
_SINGLE_BRACE_PATTERN = re.compile(r"(?<!\{)\{([a-zA-Z0-9_][^{}]*)\}(?!\})")

def _mask_snakemake_vars(code: str) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    nonce = uuid.uuid4().hex
    tokens: list[str] = []
    originals: list[str] = []

    def replace(match: re.Match[str]) -> str:
        token = f"__SNAKEFMT_{nonce}_{len(tokens)}__"
        tokens.append(token)
        originals.append(match.group(0))
        return token

    # Mask {{...}} FIRST so the lookbehind/lookahead on the single-brace
    # pattern doesn't get confused by partial matches.
    code = _DOUBLE_BRACE_PATTERN.sub(replace, code)
    code = _SINGLE_BRACE_PATTERN.sub(replace, code)
    return code, tuple(tokens), tuple(originals)
```

`_unmask_snakemake_vars` already does the right thing — iterates `(token, original)` pairs in reverse and substitutes. No signature change.

**F-string handling:** with this fix, f-strings are formatted normally. No special-case skip. The reviewer's underlying concern (wrong masking semantics for f-strings) is resolved by the unified two-layer mask.

#### C2 — Mask token line-length impact (verification)

**Source:** Hocnonsense comment #8a.

**Concern:** The mask token `__SNAKEFMT_<32hex>_<n>__` is ~50 chars. shfmt may make formatting decisions based on token-inflated line lengths, producing output that doesn't reflect real lengths post-unmask.

**Verification:** shfmt does NOT do length-based line wrapping by default. The `-i 4 -ci -bn` flags we use are syntactic only. So this should be a non-issue.

**Action:** add a test that places multiple `{var}` tokens on a single long line and asserts no spurious line breaks are introduced. Pre-existing `test_format_shell_code_many_variables` already covers token uniqueness; new test extends to length-based check.

```python
def test_format_shell_code_long_line_no_spurious_wrap():
    vars = " ".join(f"{{var{i}}}" for i in range(10))
    unformatted = f"echo {vars}\n"
    expected = unformatted
    assert format_shell_code(unformatted) == expected
```

If shfmt does wrap (unexpected), pivot to a flag that disables length wrap, with a follow-up note.

Reviewer's secondary suggestion (test that asserts UUID is not in code post-unmask): redundant with existing tests — if any token survived, the round-trip would visibly differ from the original. Skip.

#### M1 — `Snakefile.format_shell` set imperatively from CLI (maintainability)

**Source:** Hocnonsense comment #2 (`snakefmt/snakefmt.py:264`).

Currently:

```python
snakefile.format_shell = format_shell  # imperative, post-construction mutation
```

Move `format_shell` into the constructor signature, mirroring `sort_directives`. Pass through from CLI to `Formatter.__init__` (or `Parser.__init__`).

Steps:
1. Find where `sort_directives` flows from CLI → constructor. Mirror that path.
2. Update `snakefmt.py` `main` to pass `format_shell=format_shell` to the constructor.
3. Remove the imperative assignment.
4. Verify `tests/test_config.py::TestShellFormattingConfig` and `tests/test_formatter.py::TestShellBlockFormatting` still pass.

#### S1 — Regex consolidation (style)

**Source:** Hocnonsense comment #5 (`shell_formatter.py:89`).

Combine the two `re.fullmatch` calls in `format_python_string_literal`:

```python
match = re.fullmatch(r'^([a-zA-Z]*)("""|\'\'\'')([\s\S]*?)(\2)$', literal)
```

Backreference `\2` ensures the closing quote matches the opening one. No semantic change.

#### S2 — Docstring gap on no-op fallback (style)

**Source:** Hocnonsense comment #5 (second half).

`format_python_string_literal` silently returns the input unchanged on non-match. Document this in the docstring, and explicitly note that the function expects the literal to come from `str(parameter)` (caller-side guarantees no leading whitespace beyond the trailing-rstrip handled internally).

#### T1 — More edge-case tests (test coverage)

**Source:** Hocnonsense comment #7, plus the trade-offs locked in by C1.

Add to `TestShellBlockFormatting` (or a dedicated `TestShellHeredocs` class):

1. **Indent variants** — too few / too many leading spaces in source, formatted result still has consistent target indent.
2. **Basic heredoc** — `<<EOF` terminator lands at column 0 after formatting (covers B2).
3. **Indented heredoc** — `<<-EOF` body and terminator preserved correctly.
4. **Quoted heredoc** — `<<'EOF'` (terminator quoted) preserved.
5. **Heredoc with embedded `\n` and blank lines** — e.g. embedded Python heredoc preserves significant indentation.
6. **Parameter expansion `${{VAR}}`** — round-trips verbatim (most common case-2 idiom).
7. **Brace group `{{ echo hi; echo bye; }}`** — preserved verbatim but NOT internally reformatted (locks in the C1 trade-off so future contributors don't try to "fix" it without understanding).
8. **Brace expansion `{{a,b,c}}`** — preserved verbatim.
9. **F-string with `{{output}}`** — round-trips, exercising the new f-string handling.

```python
def test_heredoc_terminator_at_column_zero(self):
    snakefile = dedent('''\
        rule a:
            shell:
                """
                cat <<EOF
                line1
                EOF
                """
        ''')
    formatted = formatter(snakefile)
    assert "\nEOF\n" in formatted  # terminator at column 0 after the newline before
```

```python
def test_format_shell_code_param_expansion_round_trips():
    code = 'echo ${{VAR}} ${{VAR:-default}}\n'
    assert format_shell_code(code) == code

def test_format_shell_code_brace_group_preserved_not_internally_formatted():
    code = '{{ echo hi; echo bye; }}\n'
    # Token-masked, restored verbatim. Body not internally reformatted.
    assert format_shell_code(code) == code
```

## README addendum

Add a short note to the shell-formatting section:

> **Limitation**: bash brace groups (`{{ cmd1; cmd2; }}` in Snakefile source, `{ cmd1; cmd2; }` in bash) are preserved verbatim but their bodies are not internally reformatted by shfmt. This is intentional — the brace count must be preserved exactly so Snakemake's `str.format()` render step doesn't break. If you need internal formatting for a brace group, wrap the block in `# fmt: off` / `# fmt: on`.

## Execution Order

1. **C1** — unified two-layer mask (`{{...}}` + `{...}`). Smallest correctness fix. Adds test coverage for `{{...}}` round-trip and f-string formatting.
2. **B2** — heredoc-aware indent. Largest change. Adds `_indent_preserving_heredocs` helper.
3. **T1** — heredoc + edge-case tests, proves B2 + C1.
4. **C2** — long-line mask token verification test.
5. **M1** — constructor plumbing refactor.
6. **S1, S2** — regex consolidation + docstring cleanup.
7. **README addendum** — limitation note.

Each step ends with **`make fmt && make lint && uv run pytest -q`** to confirm green before moving to the next. Suggested commit grouping (so the PR diff stays reviewable):

- Commit 1: C1 + matching tests in `tests/test_shell_formatter.py`.
- Commit 2: B2 + heredoc tests (T1 subset).
- Commit 3: T1 remaining edge-case tests + C2.
- Commit 4: M1 refactor.
- Commit 5: S1 + S2 + README addendum.

## Out of Scope

- **Pattern tightening** — declined; would break valid Snakemake placeholders.
- **F-string skip** — initial recommendation revised; unified mask handles f-strings correctly.
- **Brace-group internal formatting** — accepted limitation, escape hatch via `# fmt: off`.
- **Multi-heredoc on one line** — accept as known limitation, document with test.
- **Heredoc detection inside quoted strings** — accept false-positive case, document.
