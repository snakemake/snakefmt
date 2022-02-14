# Snakefmt

[![GitHub Workflow Status](https://img.shields.io/github/workflow/status/snakemake/snakefmt/python_poetry_package)](https://github.com/snakemake/snakefmt/actions)
[![codecov](https://codecov.io/gh/snakemake/snakefmt/branch/master/graph/badge.svg)](https://codecov.io/gh/snakemake/snakefmt)
[![PyPI](https://img.shields.io/pypi/v/snakefmt)](https://pypi.org/project/snakefmt/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/snakefmt)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

This repository provides formatting for [Snakemake][snakemake] files. It follows the
design and specifications of [Black][black].

> **⚠️WARNING⚠️**: `snakefmt` modifies files in-place by default, thus we strongly
> recommend ensuring your files are under version control before doing any formatting.
> You
> can also pipe the file in from stdin, which will print it to the screen, or use the
> `--diff` or `--check` options. See [Usage](#usage) for more details.

[TOC]: #

# Table of Contents
- [Install](#install)
  - [PyPi](#pypi)
  - [Conda](#conda)
  - [Containers](#containers)
  - [Local](#local)
- [Example File](#example-file)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Full Usage](#full-usage)
- [Configuration](#configuration)
- [Integration](#integration)
    - [Editor Integration](#editor-integration)
    - [Version Control Integration](#version-control-integration)
    - [Github Actions](#github-actions)
- [Plug Us](#plug-us)
- [Changes](#changes)
- [Contributing](#contributing)
- [Cite](#cite)


## Install

### PyPi

```sh
pip install snakefmt
```

### Conda

[![Conda (channel only)](https://img.shields.io/conda/vn/bioconda/snakefmt)](https://anaconda.org/bioconda/snakefmt)
[![bioconda version](https://anaconda.org/bioconda/snakefmt/badges/platforms.svg)](https://anaconda.org/bioconda/snakefmt)

```sh
conda install -c bioconda snakefmt
```

### Containers

As `snakefmt` has a Conda recipe, there is a matching image built for each version by
Biocontainers.

In the following examples, all tags (`<tag>`) can be found
[here](https://quay.io/repository/biocontainers/snakefmt?tab=tags).

#### Docker

```shell
$ docker run -it "quay.io/biocontainers/snakefmt:<tag>" snakefmt --help
```

#### Singularity

```shell
$ singularity exec "docker://quay.io/biocontainers/snakefmt:<tag>" snakefmt --help
```

### Local

These instructions include [installing `poetry`](https://python-poetry.org/docs/#installation).
```sh
# install poetry
curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | python3

git clone https://github.com/snakemake/snakefmt && cd snakefmt
# install snakefmt in a new environment
poetry install
# activate the environment so snakefmt is available on your PATH
poetry shell
```

## Example File

Input

```python
from snakemake.utils import min_version
min_version("5.14.0")
configfile: "config.yaml" # snakemake keywords are treated like classes i.e. 2 newlines
SAMPLES = ['s1', 's2'] # strings are normalised
CONDITIONS = ["a", "b", "longlonglonglonglonglonglonglonglonglonglonglonglonglonglonglong"] # long lines are wrapped
include: "rules/foo.smk" # 2 newlines

rule all:
    input: "data/results.txt" # newlines after keywords enforced and trailing comma

rule gets_separated_by_two_newlines:
    input:
        files = expand("long/string/to/data/files/gets_broken_by_black/{sample}.{condition}",sample=SAMPLES, condition=CONDITIONS)
if True:
    rule can_be_inside_python_code:
        input: "parameters", "get_indented"
        threads: 4 # Numeric params stay unindented
        params: key_val = "PEP8_formatted"
        run:

                print("weirdly_spaced_string_gets_respaced")

```


Output

```python
from snakemake.utils import min_version

min_version("5.14.0")


configfile: "config.yaml" # snakemake keywords are treated like classes i.e. 2 newlines


SAMPLES = ["s1", "s2"] # strings are normalised
CONDITIONS = [
    "a",
    "b",
    "longlonglonglonglonglonglonglonglonglonglonglonglonglonglonglong",
]  # long lines are wrapped


include: "rules/foo.smk" # 2 newlines


rule all:
    input:
        "data/results.txt", # newlines after keywords enforced and trailing comma


rule gets_separated_by_two_newlines:
    input:
        files=expand(
            "long/string/to/data/files/gets_broken_by_black/{sample}.{condition}",
            sample=SAMPLES,
            condition=CONDITIONS,
        ),


if True:

    rule can_be_inside_python_code:
        input:
            "parameters",
            "get_indented",
        threads: 4 # Numeric params stay unindented
        params:
            key_val="PEP8_formatted",
        run:
            print("weirdly_spaced_string_gets_respaced")

```


## Usage

### Basic Usage

Format a single Snakefile.

```shell
snakefmt Snakefile
```

Format all Snakefiles within a directory.

```shell
snakefmt workflows/
```

Format a file but write the output to stdout.

```shell
snakefmt - < Snakefile
```

### Full Usage

```
$ snakefmt --help
Usage: snakefmt [OPTIONS] [SRC]...

  The uncompromising Snakemake code formatter.

  SRC specifies directories and files to format. Directories will be
  searched for file names that conform to the include/exclude patterns
  provided.

  Files are modified in-place by default; use diff, check, or  `snakefmt - <
  Snakefile` to avoid this.

Options:
  -l, --line-length INT  Lines longer than INT will be wrapped.  [default: 88]
  --check                Don't write the files back, just return the status.
                         Return code 0 means nothing would change. Return code
                         1 means some files would be reformatted. Return code
                         123 means there was an error.

  -d, --diff             Don't write the files back, just output a diff for
                         each file to stdout.

  --compact-diff         Same as --diff but only shows lines that would change
                         plus a few lines of context.

  --include PATTERN      A regular expression that matches files and
                         directories that should be included on recursive
                         searches.  An empty value means all files are
                         included regardless of the name.  Use forward slashes
                         for directories on all platforms (Windows, too).
                         Exclusions are calculated first, inclusions later.
                         [default: (\.smk$|^Snakefile)]

  --exclude PATTERN      A regular expression that matches files and
                         directories that should be excluded on recursive
                         searches.  An empty value means no paths are
                         excluded. Use forward slashes for directories on all
                         platforms (Windows, too). Exclusions are calculated
                         first, inclusions later.  [default: (\.snakemake|\.eg
                         gs|\.git|\.hg|\.mypy_cache|\.nox|\.tox|\.venv|\.svn|_
                         build|buck-out|build|dist)]

  -c, --config PATH      Read configuration from PATH. By default, will try to
                         read from `./pyproject.toml`

  -h, --help             Show this message and exit.
  -V, --version          Show the version and exit.
  -v, --verbose          Turns on debug-level logging.

```

## Configuration

`snakefmt` is able to read project-specific default values for its command line options
from a `pyproject.toml` file. In addition, it will also load any [`black`
configurations][black-config] you have in the same file.

By default, `snakefmt` will search in the parent directories of the formatted file(s)
for a file called `pyproject.toml` and use any configuration there.
If your configuration file is located somewhere else or called something different,
specify it using `--config`.

Any options you pass on the command line will take precedence over default values in the
configuration file.

#### Example

`pyproject.toml`

```toml
[tool.snakefmt]
line_length = 90
include = '\.smk$|^Snakefile|\.py$'

# snakefmt passes these options on to black
[tool.black]
skip_string_normalization = true
```

In this example we increase the `--line-length` value and also include python (`*.py`)
files for formatting - this effectively runs `black` on them. `snakefmt` will also pass
on the `[tool.black]` settings, internally, to `black`.


## Integration


### Editor Integration

For instructions on how to integrate `snakefmt` into your editor of choice, refer to
[`docs/editor_integration.md`](docs/editor_integration.md)

### Version Control Integration

`snakefmt` supports [pre-commit](https://pre-commit.com/), a framework for managing git pre-commit hooks. Using this framework you can run `snakefmt` whenever you commit a `Snakefile` or `*.smk` file. `Pre-commit` automatically creates an isolated virtual environment with `snakefmt` and will stop the commit if `snakefmt` would modify the file. You then review, stage, and re-commit these changes. Pre-commit is especially useful if you don't have access to a CI/CD system like GitHub actions.

To do so, create the file `.pre-commit-config.yaml` in the root of your project directory with the following:

```yaml
repos:
  - repo: https://github.com/snakemake/snakefmt
    rev: 0.5.0 # Replace by any tag/version ≥0.2.4 : https://github.com/snakemake/snakefmt/releases
    hooks:
      - id: snakefmt
```

Then [install pre-commit](https://pre-commit.com/#installation) and initialize the pre-commit hooks by running `pre-commit install` (Note you need to run this step once per clone of your repository). Additional pre-commit hooks can be found [here](https://pre-commit.com/hooks.html).

### GitHub Actions

[GitHub Actions](https://github.com/features/actions) in combination with [super-linter](https://github.com/github/super-linter) allows you to automatically run `snakefmt` on all Snakefiles in your repository e.g. whenever you push a new commit.

To do so, create the file `.github/workflows/linter.yml` in your repository:
```yaml
---
name: Lint Code Base

on:
  push:
  pull_request:
    branches: [master]

jobs:
  build:
    name: Lint Code Base
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Code
        uses: actions/checkout@v2

      - name: Lint Code Base
        uses: github/super-linter@v3
        env:
          VALIDATE_ALL_CODEBASE: false
          DEFAULT_BRANCH: master
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

          VALIDATE_SNAKEMAKE_SNAKEFMT: true
```

Additional configuration parameters can be specified by creating `.github/linters/.snakefmt.toml`:
```toml
[tool.black]
skip_string_normalization = true
```

For more information check the `super-linter` readme.

## Plug Us

If you can't get enough of badges, then feel free to show others you're using `snakefmt`
in your project.

[![Code style: snakefmt](https://img.shields.io/badge/code%20style-snakefmt-000000.svg)](https://github.com/snakemake/snakefmt)

#### Markdown

```md
[![Code style: snakefmt](https://img.shields.io/badge/code%20style-snakefmt-000000.svg)](https://github.com/snakemake/snakefmt)
```

#### ReStructuredText

```rst
.. image:: https://img.shields.io/badge/code%20style-snakefmt-000000.svg
    :target: https://github.com/snakemake/snakefmt
```

## Changes

See [`CHANGELOG.md`][changes].

## Contributing

See [CONTRIBUTING.md][contributing].

## Cite

[![DOI][doi-shield]][doi]

```Bibtex
@article{snakemake2021,
  doi = {10.12688/f1000research.29032.2},
  url = {https://doi.org/10.12688/f1000research.29032.2},
  year = {2021},
  month = apr,
  publisher = {F1000 Research Ltd},
  volume = {10},
  pages = {33},
  author = {Felix M\"{o}lder and Kim Philipp Jablonski and Brice Letcher and Michael B. Hall and Christopher H. Tomkins-Tinch and Vanessa Sochat and Jan Forster and Soohyun Lee and Sven O. Twardziok and Alexander Kanitz and Andreas Wilm and Manuel Holtgrewe and Sven Rahmann and Sven Nahnsen and Johannes K\"{o}ster},
  title = {Sustainable data analysis with Snakemake},
  journal = {F1000Research}
}
```


[snakemake]: https://snakemake.readthedocs.io/
[black]: https://black.readthedocs.io/en/stable/
[black-config]: https://github.com/psf/black#pyprojecttoml
[pyproject]: https://github.com/snakemake/snakefmt/blob/master/pyproject.toml
[poetry]: https://python-poetry.org
[contributing]: CONTRIBUTING.md
[changes]: CHANGELOG.md
[doi-shield]: https://img.shields.io/badge/DOI-10.12688%2Ff1000research.29032.2-brightgreen.svg
[doi]: https://doi.org/10.12688/f1000research.29032.2
