# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


### [0.10.1](https://www.github.com/snakemake/snakefmt/compare/v0.10.0...v0.10.1) (2024-04-15)


### Bug Fixes

* correctly find config file after updating min. black to v24.3 ([0f20494](https://www.github.com/snakemake/snakefmt/commit/0f204945d2f203ce54b434a5b2ae9c70ecfa5cdc))
* don't add spacing between consencutive braces in string [closes [#222](https://www.github.com/snakemake/snakefmt/issues/222)] ([2d28922](https://www.github.com/snakemake/snakefmt/commit/2d2892275e0c1083f67cc595a83f815e005b07df))

## [0.10.0](https://www.github.com/snakemake/snakefmt/compare/v0.9.0...v0.10.0) (2024-01-31)


### Features

* update to black v24 ([cbc6e2f](https://www.github.com/snakemake/snakefmt/commit/cbc6e2f98d97a0577219d94d75827a2eb077c771))


### Bug Fixes

* preserve double curly braces in python code [[#215](https://www.github.com/snakemake/snakefmt/issues/215)] ([1cbcfb1](https://www.github.com/snakemake/snakefmt/commit/1cbcfb1d22d7870c0e7c1201ac7cfa2e4424ec2e))

## [0.9.0](https://www.github.com/snakemake/snakefmt/compare/v0.8.5...v0.9.0) (2024-01-09)


### ⚠ BREAKING CHANGES

* update black, which bumps min. req. python

### Bug Fixes

* don't add space between string and comma [python3.12 f-string tokenize] ([18e9874](https://www.github.com/snakemake/snakefmt/commit/18e987482594bd5cb400b4ce9a54ab4fba27d956))
* don't remove double braces in f-strings in rule directives [closes [#207](https://www.github.com/snakemake/snakefmt/issues/207)] ([8b47454](https://www.github.com/snakemake/snakefmt/commit/8b4745441b9d1e5cbe762330f832bed30b08a103))
* handle python3.12 f-string tokenization [closes [#210](https://www.github.com/snakemake/snakefmt/issues/210)] ([b7e0e47](https://www.github.com/snakemake/snakefmt/commit/b7e0e47f8a76f1605d6416d35e4e0f99797ff8ec))
* improve handling of indenting in shell directive [[#186](https://www.github.com/snakemake/snakefmt/issues/186)] ([105e856](https://www.github.com/snakemake/snakefmt/commit/105e8569cd405d088adbb300ff21846d93a655ce))


### Build System

* update black, which bumps min. req. python ([022d6ab](https://www.github.com/snakemake/snakefmt/commit/022d6abb9a6edb19821fa4dcc6da7c7753f1227f))


### Continuous Integration

* correct version for next release ([f28c08d](https://www.github.com/snakemake/snakefmt/commit/f28c08dae47e4f36a702681803085990d27d3b76))

### [0.8.5](https://www.github.com/snakemake/snakefmt/compare/v0.8.4...v0.8.5) (2023-10-04)


### Bug Fixes

* make default exclude regex more specific [[#202](https://www.github.com/snakemake/snakefmt/issues/202)] ([82ef2c4](https://www.github.com/snakemake/snakefmt/commit/82ef2c47e14142469893bce6bee726058360d2e1))

### [0.8.4](https://www.github.com/snakemake/snakefmt/compare/v0.8.3...v0.8.4) (2023-04-04)


### Bug Fixes

* add localrule directive ([#187](https://www.github.com/snakemake/snakefmt/issues/187)) ([b5e25c5](https://www.github.com/snakemake/snakefmt/commit/b5e25c540bfe334c85b477376c58e39f7dd971c6))

### [0.8.3](https://www.github.com/snakemake/snakefmt/compare/v0.8.2...v0.8.3) (2023-03-15)


### Bug Fixes

* handle decorators after snakecode ([#185](https://www.github.com/snakemake/snakefmt/issues/185)) ([32d6c53](https://www.github.com/snakemake/snakefmt/commit/32d6c537eb8698d55a1ae5b98da760bd79fa5bb4))
* raise error on empty named param ([#183](https://www.github.com/snakemake/snakefmt/issues/183)) ([b5aa660](https://www.github.com/snakemake/snakefmt/commit/b5aa66052b90618c0c033c9c9e46987d4e8f1ed2))

### [0.8.2](https://www.github.com/snakemake/snakefmt/compare/v0.8.1...v0.8.2) (2023-03-08)


### Bug Fixes

* add .template to default excludes ([610762f](https://www.github.com/snakemake/snakefmt/commit/610762f133c39f771ffbb93b64a50637d8f189f5))
* dont raise NotAnIdentifier function ([#179](https://www.github.com/snakemake/snakefmt/issues/179)) ([932df73](https://www.github.com/snakemake/snakefmt/commit/932df73a175ab98ca6e179184feb98f1d5a6eeac))
* only show diff for changed files ([7b35c16](https://www.github.com/snakemake/snakefmt/commit/7b35c1604a2cab67e6c2b12ca969bcd57a9834be))

### [0.8.1](https://www.github.com/snakemake/snakefmt/compare/v0.8.0...v0.8.1) (2023-02-02)


### Bug Fixes

* collate consecutive directives after if block [[#172](https://www.github.com/snakemake/snakefmt/issues/172)] ([cbe88c7](https://www.github.com/snakemake/snakefmt/commit/cbe88c73de3dfee181da14cc0cfd4efad9f0c7a6))
* comments causing indenting issues [[#169](https://www.github.com/snakemake/snakefmt/issues/169)] ([#5](https://www.github.com/snakemake/snakefmt/issues/5)) ([e736235](https://www.github.com/snakemake/snakefmt/commit/e736235e52c1de4588fb4336beec3b7f71bdba86))
* indenation of line-wrapped code [[#171](https://www.github.com/snakemake/snakefmt/issues/171)] ([#7](https://www.github.com/snakemake/snakefmt/issues/7)) ([f524574](https://www.github.com/snakemake/snakefmt/commit/f5245745b0e5aae8162d9ab7b8df4f3a92ec8214))

### Build

* updated `black` to version `^23.1.0` ([5462512](https://github.com/snakemake/snakefmt/commit/546251258410966ada03c6562232b63521155da5))

## [0.8.0](https://www.github.com/snakemake/snakefmt/compare/v0.7.0...v0.8.0) (2022-12-19)


### Features

* add support for resource_scopes directive ([67fb11b](https://www.github.com/snakemake/snakefmt/commit/67fb11b40cb6ea5e3e6d89fcf8a367e4fbe17ada))
* add support for resource_scopes directive ([514192a](https://www.github.com/snakemake/snakefmt/commit/514192afabbf60edf3f2a800b390590c385679c8))


### Bug Fixes

* 159 ([1423e6b](https://www.github.com/snakemake/snakefmt/commit/1423e6b35377ef2431aa7400155ac69b10afb12e))
* indentation issues from [#124](https://www.github.com/snakemake/snakefmt/issues/124) ([399ec55](https://www.github.com/snakemake/snakefmt/commit/399ec55c76b2c3b7d664c90f9e8a604e47d07ee9))
* relax importlib_metadata version pin [[#162](https://www.github.com/snakemake/snakefmt/issues/162)] ([49b4f02](https://www.github.com/snakemake/snakefmt/commit/49b4f02dce21dd0964c1248a2f3114c3507831e1))
* relax importlib_metadata version pin [[#162](https://www.github.com/snakemake/snakefmt/issues/162)] ([ab91f9f](https://www.github.com/snakemake/snakefmt/commit/ab91f9f226cccf7a16a374254dc14b3e7b50ba53))

## [0.7.0](https://www.github.com/snakemake/snakefmt/compare/v0.6.1...v0.7.0) (2022-11-08)


### Features

* add support for new exclude expressions in use rule statements ([9f03019](https://www.github.com/snakemake/snakefmt/commit/9f0301994b5ea97a82d8ad88f9ce2fc18793815d))


### Bug Fixes

* do not align the inside of multiline strings [[#123](https://www.github.com/snakemake/snakefmt/issues/123)]] ([bb4aabf](https://www.github.com/snakemake/snakefmt/commit/bb4aabf801504483886c53e0e84011dd7aafe684))
* don't format r-strings [[#123](https://www.github.com/snakemake/snakefmt/issues/123)] ([bcc5371](https://www.github.com/snakemake/snakefmt/commit/bcc53716aa2b1e4576f0e34396d8620094660126))
* formatting of triple quoted strings [[#152](https://www.github.com/snakemake/snakefmt/issues/152)] ([764e11d](https://www.github.com/snakemake/snakefmt/commit/764e11df2055689776e5ab4db181d48374c022cc))
* line spacing after snakemake keyword ([beca978](https://www.github.com/snakemake/snakefmt/commit/beca9789de9457682337e6771875eae883f6f3c4))

## [unreleased]

## [0.6.1](https://www.github.com/snakemake/snakefmt/compare/v0.6.0...v0.6.1) (2022-06-13)

### Added
* Support for `retries` keyword [[#145][145]] - thanks [@maarten-k](https://github.com/maarten-k)

### Fixed
* Keyword argument lambdas are now allowed inside rules [[#135][135]]
* Improve reported line number in Snakefile when black fails to parse [[#127][127]]
* Better handling of snakemake code inside nested if-else statements with comments at differing indentation levels [[#126][126]] - a HUGE thank you to [@siebrenf](https://github.com/siebrenf) for testing

## [0.6.0](https://www.github.com/snakemake/snakefmt/compare/v0.5.0...v0.6.0) (2022-03-03)

### Added

* Support for `template_engine` keyword. **This requires bumping our minimum python version to 3.7 to allow for snakemake v7.**

## [0.5.0]

### Added
* Support for `prefix` and `default_target` keywords [[#131][131]]

### Changed
* Updated snakemake dependency to ^6.15.0
* Updated black dependency to stable version (v22.1.0). See [the release changes](https://github.com/psf/black/releases/tag/22.1.0) 
for details of style changes. This also required updating click to v8.0.0.

### Fixed
* Fix edge case for keywords inside Python if/else ([#115][115])

### Removed
* No longer raise error if multiple keywords have the same name (e.g. `rule a` used
  twice)


## [0.4.4]

### Fixed
* Collapsing of multi-line strings does not cause syntax error now [[#118][118]]
* Version detection adapts to python version
* Single-quoted multi-line strings are now supported [[#121][121]]

## [0.4.3]

### Added
* Missing `handover` rule keyword that was added in
  [`snakemake` v6.2.0](https://github.com/snakemake/snakemake/blob/main/CHANGELOG.rst#620---2021-04-22)

### Changed
* Upgraded minimum `black` version to 21.7b0 [[#116][116]] (@jalaziz)

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
[unreleased]: https://github.com/snakemake/snakefmt/compare/0.6.1...HEAD
[0.6.1]: https://www.github.com/snakemake/snakefmt/compare/v0.6.0...v0.6.1
[0.6.0]: https://www.github.com/snakemake/snakefmt/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/snakemake/snakefmt/releases/tag/0.5.0
[0.4.4]: https://github.com/snakemake/snakefmt/releases/tag/0.4.4
[0.4.3]: https://github.com/snakemake/snakefmt/releases/tag/0.4.3
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
[115]: https://github.com/snakemake/snakefmt/issues/115
[116]: https://github.com/snakemake/snakefmt/pull/116
[118]: https://github.com/snakemake/snakefmt/issues/118
[121]: https://github.com/snakemake/snakefmt/issues/121
[126]: https://github.com/snakemake/snakefmt/issues/126
[127]: https://github.com/snakemake/snakefmt/issues/127
[131]: https://github.com/snakemake/snakefmt/pull/131
[135]: https://github.com/snakemake/snakefmt/issues/135
[145]: https://github.com/snakemake/snakefmt/pull/145
