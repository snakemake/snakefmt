# Plan: Fix trailing-newline bug in shell formatting

- **Date:** 2026-05-13
- **Branch:** `feat/shfmt`
- **Related:** ADR-0001 (shell-formatter distribution), GitHub issue #170

## 1. Diagnosis

Root cause: `format_python_string_literal` in `snakefmt/shell_formatter.py`
uses `re.fullmatch(r'^([a-zA-Z]*)(""")([\s\S]*?)(\2)$', literal)`, which
requires the literal to end **exactly** at the closing `"""`. The caller at
`snakefmt/formatter.py:407` builds `val = str(parameter)`, and the parser
emits a `NEWLINE` token after the closing triple-quote, so the literal that
arrives at the helper looks like `'"""...\n        """\n'`.

The regex `fullmatch` rejects this (trailing `\n` not consumed by `$`), the
helper returns its input unchanged, and shell formatting becomes a silent
end-to-end no-op in real `snakefmt` runs.

Unit tests in `tests/test_shell_formatter.py` pass because they hand-build
literals **without** the trailing newline. The integration test gap is the
reason the bug shipped.

Evidence (traced 2026-05-13):

```text
IN  startswith """: True endswith """: False len: 210
IN repr: '"""\n        bwa mem ...\n        """\n'
CHANGED: False
```

With `literal.rstrip()` applied before regex match, formatting fires
correctly.

## 2. TDD red — write failing tests first

### 2a. Helper robustness suite

Location: `tests/test_shell_formatter.py`.

One parametrized test asserting `format_python_string_literal` reformats its
content (i.e., does **not** return its input unchanged) for each of these
input shapes:

1. Trailing `\n` after closing `"""` — the actual bug.
2. Multiple trailing newlines (`\n\n`).
3. Trailing spaces / tabs after closing `"""`.
4. `\r\n` line endings inside the literal.
5. String prefix variants: `f"""`, `rb"""`, `B"""`, `u"""`, and bare `"""`.

### 2b. End-to-end behavioural set

Location: `tests/test_formatter.py`, new `TestShellBlockFormatting` class
(or equivalent). All cases drive a Snakefile through the public formatter
(`setup_formatter`) and assert on the rendered output.

1. **Default-on formats.** Snakefile with messy `shell:` block in; shfmt-
   formatted shell content out; no flags touched.
2. **`format_shell = False` disables.** Same Snakefile input; attribute set
   `False`; shell content rendered unchanged from input.
3. **Config-driven disable.** `format_shell = false` in TOML config exercises
   the CLI plumbing path. Probably lives in `tests/test_config.py` or
   `tests/test_main.py`.
4. **`{var}` masking preserved end-to-end.** Snakefile body contains
   `{input}`, `{output}`, and escaped `{{print $1}}`. Assert all three
   survive parser → formatter → shfmt round-trip verbatim.
5. **`# fmt: off` opts out of shell formatting.** Shell block wrapped
   between `# fmt: off` / `# fmt: on`; content untouched.

All new tests **must fail (RED)** before the fix is applied — confirms the
bug and prevents the fix from being a vacuous green.

## 3. Fix

Single edit in `snakefmt/shell_formatter.py`:

```python
def format_python_string_literal(literal: str, target_indent: int = 0) -> str:
    literal = literal.rstrip()  # NEW: tolerate trailing whitespace from parser
    match = re.fullmatch(r'^([a-zA-Z]*)(""")([\s\S]*?)(\2)$', literal)
    ...
```

The caller already `rstrip`s `val` at `formatter.py:418`, so trailing
whitespace was always going to be discarded — stripping it earlier inside the
helper just lets the regex see a parseable shape. No behavioural change
downstream.

## 4. Triage existing test breakage — per-test (option P)

Run `uv run pytest`. For every test in `tests/test_formatter.py` that breaks
after the fix:

- **Test is about shell formatting itself** (assertions reference shell body
  shape, indentation, line wrapping inside `shell:`) → update the expected
  string to reflect shfmt's output. The old expectation was a fossil of the
  bug.
- **Test is about something else** (directive sorting, comment placement,
  indentation outside the shell block, etc.) and the shell content is
  incidental → add `snakefile.format_shell = False` to preserve the test's
  original intent. Pattern already exists at `tests/test_formatter.py:868,
  900, 918`.

Document the per-test decisions in the commit message so a reviewer can
trace why each expected string changed.

## 5. Verify

- `uv run pytest` — all existing + new tests green.
- Manual smoke: run `snakefmt` on a sample Snakefile with a messy `shell:`
  block; confirm reformatting fires end-to-end.

## 6. Explicit non-goals

- No regex rewrite — `rstrip` is sufficient.
- No new shfmt flags.
- No performance / caching work.
- No fixes to `format_python_string_literal`'s indentation handling beyond
  what the bug demands.
- No changes to the seam structure introduced in the earlier refactor
  (`_mask_snakemake_vars`, `_invoke_shfmt`, `_unmask_snakemake_vars`).

## 7. Risks and open questions

- **Unknown count of broken existing tests.** Cannot pre-count without
  running pytest after the fix. If the count is large (>20), reconsider
  option Q (blanket opt-out in `setup_formatter` default) — but only after
  seeing the actual breakage shape.
- **`# fmt: off` interaction is unverified.** Test 2b.5 will resolve this;
  if it fails, a separate fix may be needed.
- **Config-path test (2b.3) location.** Will be decided at implementation
  time depending on what `tests/test_config.py` and `tests/test_main.py`
  already cover.
