Refactor behaviour differences
===

Comparison of `refactor-parser` against `master` on 549 `Snakefile` / `*.smk` files from the snakemake repository (1c67a66cb), with `sort_directives=True` and `format_shell=True`:

- both succeed: 529
- identical output: 476
- different output: 53
- only master succeeds: 0
- only refactor succeeds: 7
- both fail: 13

The remaining differences come from the new block/tokenizer architecture.

## Blank-only differences (44)

- Leading blank lines are stripped: 34 files.
- Blank lines inside `run:` bodies are preserved: 7 files.
- No blank line between consecutive `use rule` lines: 3 files.

## Comment-only differences (2)

- Comment spacing is normalised, e.g. `#foo` to `# foo`.

## Other differences (7)

- `tests/test_access_patterns/Snakefile`: long list parameter with a trailing
  comment is wrapped the way Black wraps it.
- `candidate_calling.smk`: multiline conditional parameter is parenthesised and
  gets a trailing comma; trailing comment whitespace is removed.
- `tests/test_delete_output/Snakefile`, `tests/test_issue1092/Snakefile`:
  comments before `run:` stay attached to `run:`.
- `tests/test01/Snakefile`: inline comment stays on the actual commented part of
  an implicit string concatenation.
- `examples/c/src/Snakefile`: a leading rule docstring is emitted before the
  directives.
- `tests/test_github_issue806/Snakefile`: a lambda fits on one line where master
  split it.

## Intentional simplification

- A rule docstring followed by a comment no longer gets a blank line inserted between them. `master` inserted it because the old formatter passed the rule docstring to Black as a module-level docstring; the block formatter does not reproduce that side effect. The old test was replaced with one that asserts the simplified output.

## `use rule` comma formatting

- `use rule a, b from m` is newly accepted by the refactor. `master` rejects this multi-rule form. Its rule names are also rendered as `a, b`.
