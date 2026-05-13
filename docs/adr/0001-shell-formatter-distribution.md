# ADR-0001: Distribution mechanism for the `shfmt` dependency

- **Status:** Accepted
- **Date:** 2026-05-13

## Context

`snakefmt` formats the body of Snakemake `shell:` directives by invoking
[`shfmt`](https://github.com/mvdan/sh), a Go binary that formats POSIX shell,
Bash, and (since 3.13) Zsh. The integration is implemented in
`snakefmt/shell_formatter.py` and shells out to the `shfmt` executable via
`subprocess.run`.

The Go binary is currently delivered as a Python wheel by
[`shfmt-py`](https://github.com/MaxWinterstein/shfmt-py), pinned in
`pyproject.toml` as `shfmt-py>=3.12.0.2`. `shfmt-py` mirrors upstream `shfmt`
releases by downloading the official release artefact and packaging it inside a
wheel that installs an `shfmt` console script onto `PATH`, in the same way
`shellcheck-py` does for ShellCheck.

`shfmt-py` is maintained by a single author and currently lags upstream by one
minor version (`3.12.0` vs `shfmt` 3.13.1 at the time of writing). This
prompted a review of the distribution mechanism: should `snakefmt` continue to
depend on `shfmt-py`, or should it own its `shfmt` delivery so it can decouple
from a single-maintainer upstream?

### Alternatives considered

1. **Fork `shfmt-py` (or build an equivalent wheel-vendoring package).**
   `snakefmt` would publish wheels that bundle the `shfmt` binary for each
   supported platform. This is the most direct path to distribution control —
   `snakefmt` could ship a newer `shfmt` whenever it wants and is no longer
   blocked by `shfmt-py`'s release cadence. The cost is permanent maintenance
   of a wheel matrix (linux x86_64/arm64, macOS x86_64/arm64) and a CI pipeline
   that tracks upstream `shfmt` releases.

2. **Native Go bindings to `shfmt`'s formatter API.** `shfmt` exposes its
   formatter as a Go library. A binding via `gopy`/`cgo` would eliminate the
   `subprocess` hop, give us in-process error handling, and remove the
   `shfmt-py` dependency entirely. The cost is substantial: a new Go toolchain
   in CI, a separate binding repository, and platform-specific build artefacts.
   The performance win is also speculative — at typical Snakefile sizes (tens
   of `shell:` directives), `subprocess` overhead is not a measured problem.

3. **Keep `shfmt-py`.** No upfront work. We continue to consume upstream
   `shfmt` via the existing wheel and accept that we are coupled to
   `shfmt-py`'s release cadence and continued maintenance.

## Decision

**We continue to depend on `shfmt-py`.** No additional distribution work is
undertaken until one of the revisit triggers below fires. The integration
point in `snakefmt/shell_formatter.py` is structured so that swapping the
backend later is a single-function change: `_invoke_shfmt` is the seam, and the
masking logic that adapts Snakemake placeholders for shell parsers is shared
across any future backend.

## Consequences

- `snakefmt` continues to inherit `shfmt-py`'s release cadence and platform
  support matrix. As of writing, that means linux + macOS wheels, which matches
  `snakefmt`'s CI matrix (`ubuntu-latest`, `macos-latest`).
- We accept that `snakefmt` may lag upstream `shfmt` by one or more minor
  versions. `shfmt`'s format output is stable across the 3.x series, so this
  is not a correctness issue for the formatted output users will see.
- The `subprocess` hop per `shell:` directive is preserved. At typical
  Snakefile sizes this has not been observed to be a user-visible cost.
- The shell-formatter call site is structured so that, if any of the revisit
  triggers fires, the replacement work is contained to the implementation of
  `_invoke_shfmt` (or its successor) in `snakefmt/shell_formatter.py`.

## Revisit triggers

This decision should be re-opened if any of the following occur:

1. **A reported formatting bug is fixed in an upstream `shfmt` release**
   that `shfmt-py` has not shipped within ~60 days of the upstream tag.
2. **`shfmt-py` is unpublished from PyPI** or its source repository is
   archived or marked deprecated.
3. **A wheel for a platform `snakefmt` supports** (linux x86_64/arm64,
   macOS x86_64/arm64) stops being published on a `shfmt-py` release.
4. **`snakefmt` itself starts to depend on `shfmt` features** that are newer
   than what `shfmt-py` ships — for example, surfacing a flag introduced in a
   later upstream minor.

### Non-triggers

The following are explicitly *not* reasons to revisit this decision:

- **`shfmt-py` is N minor versions behind upstream.** `shfmt`'s formatting
  behaviour is stable across the 3.x line; version lag alone does not affect
  users' formatted output. Only concrete bug fixes or feature needs (trigger 1
  or 4 above) justify the maintenance cost of owning distribution.
