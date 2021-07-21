# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [unreleased]

## [0.4.2]

### Fixed

* Three parsing-related bugs:
  - Complex lambda function syntax ([#108][108])
  - Argument unpacking ([#109][109])
  - Multiline parameters ([#111][111])

## [0.4.1]

### Fixed

* Add support for multiple anonymous rules, as per [snakemake grammar][snakemake_grammar] ([#103][103])
* Newline bug in `use` syntax ([#106][106])

## [0.4.0]

### Added

* Support for module syntax: `module` keyword and `use rule` syntax ([#99][99])
* Support for `containerized` keyword

### Changed

* Updated snakemake dependency to ^6.0.0 ([#99][99])

## [0.3.1]

### Fixed

- Support nested python code following python/snakemake nested code ([#96][96])

### Removed

- `Dockerfile` has been removed as the
  [biocontainers](https://hub.docker.com/r/snakemake/snakefmt/tags) images are smaller
  and some recent changes to the `cryptography` dependency require Rust to be installed
  (on Alpine) which further bloats our DockerHub image.

## [0.3.0]

### Changed
- Update click, toml and black (major version) to latest releases (@jlewis91)
  [[#97][97]]

## [0.2.6]

### Fixed
* Remove use of a Python 3.8-only `logging` module feature ([#89][89])
* Update Python support to ^3.6.1 due to use of `typing` module `NamedTuple`s
* Better support for python/snakemake interspersed code ([#91][91]; [#93][93])

## [0.2.5]

### Added
- Documentation for integration with Visual Studio Code ([#80][80]; thanks @austinkeller)
- Issue warnings for comment-related formatting ([#85][85])
- File-specific logging: warnings and errors during reformatting now automatically refer to the raising source file.
### Fixed
Better comment-related formatting ([#85][85]; thanks @dlaehnemann):
- PEP8 inline comment formatting: use 2 spaces
- Comments above keywords stay untouched
- Inline comments in inline-formatted keywords get relocated above
  keyword

## [0.2.4]

### Added

- `pre-commit` hook integration (@jfear)

### Fixed

- Proper indentation of nested if/else python code mixed with snakemake keywords [[#78][78]]

### Changed

- Vim plugin imports: `snakefmt` and `black` module imports raise distinct errors (@dcroote)

## [0.2.3]

### Added

- Add a vim plugin to `snakefmt` [[#62][62]] and instructions to use it
- New searching for project configuration. Used to look for `pyproject.toml` in current working directory, now recursively search for it in directories of formatted file(s).

## [0.2.2]

### Fixed

- `black` config was not being used if it did not contain `[tool.snakefmt]` [[#73][73]]
- better handling of `black.FileMode` params [[#73][73]]

## [0.2.1]

### Added

- new `scattergather` directive to the grammar [[#74][74]]

## [0.2.0]

### Added

- repeated top-level, single-parameter keywords get placed on consecutive lines [[#67][67]]

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

[snakemake_grammar]: https://snakemake.readthedocs.io/en/stable/snakefiles/writing_snakefiles.html#grammar
[unreleased]: https://github.com/snakemake/snakefmt/compare/0.4.2...HEAD
[0.4.2]: https://github.com/snakemake/snakefmt/releases/tag/0.4.2
[0.4.1]: https://github.com/snakemake/snakefmt/releases/tag/0.4.1
[0.4.0]: https://github.com/snakemake/snakefmt/releases/tag/0.4.0
[0.3.1]: https://github.com/snakemake/snakefmt/releases/tag/0.3.1
[0.3.0]: https://github.com/snakemake/snakefmt/releases/tag/0.3.0
[0.2.6]: https://github.com/snakemake/snakefmt/releases/tag/0.2.6
[0.2.5]: https://github.com/snakemake/snakefmt/releases/tag/0.2.5
[0.2.4]: https://github.com/snakemake/snakefmt/releases/tag/0.2.4
[0.2.3]: https://github.com/snakemake/snakefmt/releases/tag/0.2.3
[0.2.2]: https://github.com/snakemake/snakefmt/releases/tag/0.2.2
[0.2.1]: https://github.com/snakemake/snakefmt/releases/tag/0.2.1
[0.2.0]: https://github.com/snakemake/snakefmt/releases/tag/0.2.0
[0.1.5]: https://github.com/snakemake/snakefmt/releases/tag/0.1.5
[0.1.4]: https://github.com/snakemake/snakefmt/releases/tag/0.1.4
[0.1.3]: https://github.com/snakemake/snakefmt/releases/tag/0.1.3
[0.1.2]: https://github.com/snakemake/snakefmt/releases/tag/0.1.2
[0.1.1]: https://github.com/snakemake/snakefmt/releases/tag/0.1.1
[0.1.0]: https://github.com/snakemake/snakefmt/releases/tag/0.1.0

[55]: https://github.com/snakemake/snakefmt/issues/55
[59]: https://github.com/snakemake/snakefmt/issues/59
[61]: https://github.com/snakemake/snakefmt/issues/61
[62]: https://github.com/snakemake/snakefmt/issues/62
[65]: https://github.com/snakemake/snakefmt/issues/65
[67]: https://github.com/snakemake/snakefmt/issues/67
[68]: https://github.com/snakemake/snakefmt/issues/68
[73]: https://github.com/snakemake/snakefmt/issues/73
[74]: https://github.com/snakemake/snakefmt/pull/74
[78]: https://github.com/snakemake/snakefmt/issues/78
[80]: https://github.com/snakemake/snakefmt/issues/80
[85]: https://github.com/snakemake/snakefmt/issues/85
[89]: https://github.com/snakemake/snakefmt/issues/89
[91]: https://github.com/snakemake/snakefmt/issues/91
[93]: https://github.com/snakemake/snakefmt/issues/93
[96]: https://github.com/snakemake/snakefmt/issues/96
[97]: https://github.com/snakemake/snakefmt/pull/97
[99]: https://github.com/snakemake/snakefmt/issues/99
[106]: https://github.com/snakemake/snakefmt/issues/106
[108]: https://github.com/snakemake/snakefmt/issues/108
[109]: https://github.com/snakemake/snakefmt/issues/109
[111]: https://github.com/snakemake/snakefmt/issues/111
