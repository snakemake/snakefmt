# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

### Changed

- allow `--check` and `--diff` to be used together [[#68][68]]

## [0.1.5]

### Fixed

- dedented comments were being tied to previous indented context in `run` directive
  [[#61][61]]
- single version sourcing from pyproject.toml was failing on `pip install`ed
  distributions [[#65][65]]. Fixed by using importlib_metadata.

## [0.1.4]

### Fixed

- Add parsing support for format and raw (f/r) triple-quoted strings [[#59][59]].

## [0.1.3]

### Fixed

- Version was not correctly updated in [0.1.2].

## [0.1.2]

This release will potentially produce different output to previous versions. Previously,
when passing code to `black` for formatting, we were not allowing for the indentation
level of the code. For example, if a line has an indentation level of two and the code
is 40 character long, the line is 48 characters long. However, we were only passing the
40 characters of code to `black` meaning, in the running example, if you had set
`--line-length 45` the line would not have been formatted. This behaviour is now fixed.

### Changed

- When passing code to `black`, reduce the line length by the indentation level.

## [0.1.1]

### Fixed

- f-strings with triple quotes are now correctly handled [[#55][55]]

## [0.1.0]

### Added

- First release - so everything you see is new!

[unreleased]: https://github.com/snakemake/snakefmt/compare/0.1.5...HEAD
[0.1.5]: https://github.com/snakemake/snakefmt/releases/tag/0.1.5
[0.1.4]: https://github.com/snakemake/snakefmt/releases/tag/0.1.4
[0.1.3]: https://github.com/snakemake/snakefmt/releases/tag/0.1.3
[0.1.2]: https://github.com/snakemake/snakefmt/releases/tag/0.1.2
[0.1.1]: https://github.com/snakemake/snakefmt/releases/tag/0.1.1
[0.1.0]: https://github.com/snakemake/snakefmt/releases/tag/0.1.0

[55]: https://github.com/snakemake/snakefmt/issues/55
[59]: https://github.com/snakemake/snakefmt/issues/59
[61]: https://github.com/snakemake/snakefmt/issues/61
[65]: https://github.com/snakemake/snakefmt/issues/65
[68]: https://github.com/snakemake/snakefmt/issues/68

