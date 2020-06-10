# Snakefmt

[![GitHub Workflow Status](https://img.shields.io/github/workflow/status/snakemake/snakefmt/python_poetry_package)](https://github.com/snakemake/snakefmt/actions)
[![codecov](https://codecov.io/gh/snakemake/snakefmt/branch/master/graph/badge.svg)](https://codecov.io/gh/snakemake/snakefmt)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
![Python versions](https://img.shields.io/badge/Python%20versions->=3.6-blue)

This repository provides formatting for [Snakemake][snakemake] files. It follows the
design and specifications of [Black][black].

> **⚠️WARNING⚠️**: `snakefmt` modifies files in-place by default, thus we strongly
> recommend ensuring your files are under version control before doing any formatting.
> This is also to protect you from bugs as the project is still new. Alternatively, you
> can pipe the file in from stdin, which will print it to the screen, or use the
> `--diff` option. See [Usage](#usage) for more details.

[TOC]: #

# Table of Contents
- [Install](#install)
- [Example File](#example-file)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Full Usage](#full-usage)
- [Configuration](#configuration)
- [Design](#design)
  - [Syntax](#syntax)
  - [Formatting](#formatting)
- [Editor Integration](#editor-integration)
- [Plug Us](#plug-us)
- [Changes](#changes)
- [Contributing](#contributing)


## Install

```shell
git clone https://github.com/snakemake/snakefmt
python3 -m pip install poetry
cd snakefmt && poetry install
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

#### Check

##### `--check`

Does not write any formatted code back to file. It will instead check whether any
changes *would* be made. It returns one of three possible exit codes:

**0** - indicates **no changes** would be made

```
$ echo 'include: "foo.txt"' | snakefmt --check -                                        
[INFO] 1 file(s) would be left unchanged 🎉
$ echo "Exit code: $?"
Exit code: 0
```

**1** - indicates **changes** would be made

```
$ echo 'include:"foo.txt"' | snakefmt --check - 
[INFO] 1 file(s) would be changed 😬
$ echo "Exit code: $?"
Exit code: 1
```

**123** - indicates there was an **error** such as invalid syntax

```
$ echo 'include:' | snakefmt --check -            
[ERROR] L2: In include definition.
[INFO] 1 file(s) contains errors 🤕
$ echo "Exit code: $?"
Exit code: 123
```

#### Compact diff

##### `--compact-diff`

Does not write any formatted code back to file. It will instead print a compact diff of
how the code looks before and after formatting. The diff is compact as it only prints
the lines that will change, with a few lines of surrounding context.

```
$ echo 'x = 1\ny = 3\n\n\nrule foo:\n\tinput: "foo.txt"' | snakefmt --compact-diff -
=====> Diff for stdin <=====

--- original
+++ new
@@ -3,4 +3,5 @@
 
 
 rule foo:
-       input: "foo.txt"
+    input:
+        "foo.txt",

[INFO] All done 🎉
```

The above example shows that the variable assignments at the beginning of the file are
not included in the compact diff (but would be included in a full diff).

#### Diff

##### `--diff`

Does not write any formatted code back to file. It will instead print a diff of how the
code looks before and after formatting.

```
$ echo 'rule foo:\n\tinput: "foo.txt"' | snakefmt --diff -
=====> Diff for stdin <=====

  rule foo:
-       input: "foo.txt"
+     input:
+         "foo.txt",

[INFO] All done 🎉
```

If multiple files are specified, a diff for each file is written to stdout, separated by
`=====> Diff for <filepath> <=====`.

## Configuration

`snakefmt` is able to read project-specific default values for its command line options
from a `pyproject.toml` file. In addition, it will also load any [`black`
configurations][black-config] you have in the same file.

By default, `snakefmt` will search in your current directory for a file named
`pyproject.toml`. If your configuration file is located somewhere else or called
something different, then specify the location with `--config`.

Any options you pass on the command line will take precedence over default values in the
configuration file.

#### Example

`pyproject.toml`

```toml
[tool.snakefmt]
line-length = 90
include = '\.smk$|^Snakefile|\.py$'

# snakefmt passes these options on to black
[tool.black]
target-version = ["py37"]
```

In this example we increase the `--line-length` value and also include python (`*.py`)
files for formatting - this effectively runs `black` on them. `snakefmt` will also pass
on the `[tool.black]` settings, internally, to `black`.

## Design

### Syntax

`snakefmt`'s parser will spot syntax errors in your snakefiles:

* Unrecognised keywords
* Duplicate keywords
* Invalid parameters
* Invalid python code

But `snakefmt` not complaining does not guarantee your file is entirely error-free.

### Formatting

Python code is `black`ed.

Snakemake-specific syntax is formatted following the same principles: see [PEP8][PEP8].

## Editor Integration

For instructions on how to integrate `snakefmt` into your editor of choice, refer to
[`docs/editor_integration.md`](docs/editor_integration.md)

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

Please refer to [CONTRIBUTING.md][contributing].


[snakemake]: https://snakemake.readthedocs.io/
[black]: https://black.readthedocs.io/en/stable/
[PEP8]: https://www.python.org/dev/peps/pep-0008/
[pyproject]: https://github.com/snakemake/snakefmt/blob/master/pyproject.toml
[poetry]: https://python-poetry.org
[contributing]: CONTRIBUTING.md
[changes]: CHANGELOG.md
[black-config]: https://github.com/psf/black#pyprojecttoml

