# Snakefmt

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/snakemake/snakefmt/ci.yaml?branch=master)
[![codecov](https://codecov.io/gh/snakemake/snakefmt/branch/master/graph/badge.svg)](https://codecov.io/gh/snakemake/snakefmt)
[![PyPI](https://img.shields.io/pypi/v/snakefmt)](https://pypi.org/project/snakefmt/)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/snakefmt)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

This repository provides formatting for [Snakemake][snakemake] files. It follows the
design and specifications of [Black][black].

> [!WARNING]
> `snakefmt` modifies files in-place by default, thus we strongly
> recommend ensuring your files are under version control before doing any formatting.
> You can also pipe the file in from stdin, which will print it to the screen, or use the
> `--diff` or `--check` options. See [Usage](#usage) for more details.

> [!IMPORTANT]
> **Recent Changes:**
> 1. **Rule and module directives are now sorted by default:** `snakefmt` will automatically sort the order of directives inside rules (e.g. `input`, `output`, `shell`) and modules into a consistent order. You can opt out of this by using the `--no-sort` CLI flag.
> 2. **Black upgraded to v26:** The underlying `black` formatter has been upgraded to v26. You will see changes in how implicitly concatenated strings are wrapped (they are now collapsed onto a single line if they fit within the line limit) and other minor adjustments compared to previous versions.
> 3. **Shell blocks are now formatted using `shfmt`:** `snakefmt` now formats the body of `shell:` directives using [`shfmt`](https://github.com/mvdan/sh). This is enabled by default and will reformat shell code that was previously left untouched. You can opt out with `--no-format-shell` (`-F`) or `format_shell = false` in `pyproject.toml`. See [Shell Block Formatting](#shell-block-formatting) for details.
>
> **Example of expected differences:**
> ```python
> # Before (Snakefmt older versions)
> rule example:
>     shell:
>         "for i in $(seq 1 5);"
>         "do echo $i;"
>         "done"
>     output:
>         "b.txt",
>     input:
>         "a.txt",
>
> # After (Directives sorted, strings collapsed by Black 26)
> rule example:
>     input:
>         "a.txt",
>     output:
>         "b.txt",
>     shell:
>         "for i in $(seq 1 5);" "do echo $i;" "done"
> ```

[TOC]: #

## Table of Contents
- [Install](#install)
  - [PyPi](#pypi)
  - [Conda](#conda)
  - [Containers](#containers)
  - [Local](#local)
- [Example File](#example-file)
- [Usage](#usage)
  - [Basic Usage](#basic-usage)
  - [Full Usage](#full-usage)
  - [Shell Block Formatting](#shell-block-formatting)
  - [Directive Sorting](#directive-sorting)
  - [Format Directives](#format-directives)
  - [Configuration](#configuration)
- [Integration](#integration)
  - [Editor Integration](#editor-integration)
  - [Version Control Integration](#version-control-integration)
  - [GitHub Actions](#github-actions)
- [Plug Us](#plug-us)
  - [Markdown](#markdown)
  - [ReStructuredText](#restructuredtext)
- [Changes](#changes)
- [Contributing](#contributing)
- [Cite](#cite)


## Install

### PyPi


![PyPI - Python Version](https://img.shields.io/pypi/pyversions/snakefmt)
![PyPI - Version](https://img.shields.io/pypi/v/snakefmt)
![PyPI - Downloads](https://img.shields.io/pypi/dm/snakefmt)

```sh
pip install snakefmt
```

### Conda

[![Conda (channel only)](https://img.shields.io/conda/vn/bioconda/snakefmt)](https://anaconda.org/bioconda/snakefmt)
[![bioconda version](https://anaconda.org/bioconda/snakefmt/badges/platforms.svg)](https://anaconda.org/bioconda/snakefmt)
![Conda Downloads](https://img.shields.io/conda/dn/bioconda/snakefmt)

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

These instructions include [installing `uv`](https://docs.astral.sh/uv/getting-started/installation/).
```sh
# install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

git clone https://github.com/snakemake/snakefmt && cd snakefmt
# install snakefmt in a new environment
make install
# you can now run snakefmt with
uv run snakefmt --help
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

<details>
<summary>Show full help output</summary>

```
$ snakefmt --help
Usage: snakefmt [OPTIONS] [SRC]...

  The uncompromising Snakemake code formatter.

  SRC specifies directories and files to format. Directories will be searched
  for file names that conform to the include/exclude patterns provided.

  Files are modified in-place by default; use diff, check, or  `snakefmt - <
  Snakefile` to avoid this.

Options:
  -l, --line-length INT           Lines longer than INT will be wrapped.
                                  [default: 88]
  -s, --sort / -S, --no-sort      Sort directives in rules and modules.
                                  [default: sort]
  -f, --format-shell / -F, --no-format-shell
                                  Format shell directives using shfmt.
                                  [default: format-shell]
  --check                         Don't write the files back, just return the
                                  status. Return code 0 means nothing would
                                  change. Return code 1 means some files would
                                  be reformatted. Return code 123 means there
                                  was an error.
  -d, --diff                      Don't write the files back, just output a
                                  diff for each file to stdout.
  --compact-diff                  Same as --diff but only shows lines that
                                  would change plus a few lines of context.
  --include PATTERN               A regular expression that matches files and
                                  directories that should be included on
                                  recursive searches.  An empty value means
                                  all files are included regardless of the
                                  name.  Use forward slashes for directories
                                  on all platforms (Windows, too).  Exclusions
                                  are calculated first, inclusions later.
                                  [default: (\.smk$|^Snakefile)]
  --exclude PATTERN               A regular expression that matches files and
                                  directories that should be excluded on
                                  recursive searches.  An empty value means no
                                  paths are excluded. Use forward slashes for
                                  directories on all platforms (Windows, too).
                                  Exclusions are calculated first, inclusions
                                  later.  [default: (\.snakemake/|\.eggs/|\.gi
                                  t/|\.hg/|\.mypy_cache/|\.nox/|\.tox/|\.venv/
                                  |\.svn/|_build/|buck-
                                  out/|/build/|/dist/|\.template/)]
  -c, --config PATH               Read configuration from PATH. By default,
                                  will try to read from `./pyproject.toml`
  -h, --help                      Show this message and exit.
  -V, --version                   Show the version and exit.
  -v, --verbose                   Turns on debug-level logger.
```

</details>

### Directive Sorting

By default, `snakefmt` sorts rule and module directives (like `input`, `output`, `shell`, etc.) into a consistent order. This makes rules easier to read and allows for quicker cross-referencing between inputs, outputs, and the resources used by the execution command.

<details>
<summary>Directive ordering details</summary>

Directives are grouped by their functional role in the following order:

1.  **Identity & Early Control**: `name`, `default_target`
2.  **I/O Contract**: `input`, `output`, `log`, `benchmark`
3.  **Wildcard & Path Qualification**: `wildcard_constraints`, `pathvars`
4.  **Scheduling & Control**: `priority`, `retries`, `group`, `localrule`, `cache`, `handover`
5.  **Execution Environment**: `shadow`, `conda`, `container`, `singularity`, `containerized`, `envmodules`
6.  **Execution Resources & Parameters**: `threads`, `resources`, `params`
7.  **Annotation / Runtime Display**: `message`
8.  **Action**: `shell`, `run`, `script`, `notebook`, `wrapper`, `cwl`, `template_engine`

This ordering ensures that the directives most frequently used in execution blocks (like `threads`, `resources`, and `params`) are placed immediately above the action directive.

</details>

You can disable this feature using the `--no-sort` flag.

### Shell Block Formatting

By default, `snakefmt` formats the body of `shell:` directives using [`shfmt`](https://github.com/mvdan/sh).
This keeps shell snippets in your Snakefiles formatted consistently and avoids cosmetic diffs triggering unnecessary Snakemake re-runs.

#### Example

Before:

```python
rule align:
    input:
        "reads.fq",
    output:
        "aligned.bam",
    threads: 4
    shell:
        """
        bwa mem -t {threads} ref.fa {input} | samtools sort -o {output} -
        if [ -s {output} ]
        then
        echo "done"
        else
        echo "empty"
        exit 1
        fi
        """
```

After:

```python
rule align:
    input:
        "reads.fq",
    output:
        "aligned.bam",
    threads: 4
    shell:
        """
        bwa mem -t {threads} ref.fa {input} | samtools sort -o {output} -
        if [ -s {output} ]; then
            echo "done"
        else
            echo "empty"
            exit 1
        fi
        """
```

#### Disabling

You can disable shell formatting on the command line with `--no-format-shell` (`-F`), or in `pyproject.toml`:

```toml
[tool.snakefmt]
format_shell = false
```

`shfmt` is invoked with `-i 4 -ci -bn` (four-space indentation, indented switch cases, binary operators may start a line).

<details>
<summary>Advanced details: placeholders, heredocs, brace groups, invalid shell</summary>

#### Snakemake placeholders

Snakemake `{var}` placeholders are masked before `shfmt` runs so it does not mis-parse them, then restored verbatim afterwards.
Escaped double-brace placeholders such as those required by `awk` are passed through unchanged:

```python
rule example:
    shell:
        """
        awk '{{print $1}}' {input} > {output}
        """
```

#### Brace groups

Bash brace groups (`{ cmd1; cmd2; }`) appear as `{{ cmd1; cmd2; }}` in Snakemake shell strings
because Snakemake renders the block through `str.format()`, which requires `{{` / `}}` to produce
literal `{` / `}`. `snakefmt` preserves these double-brace sequences verbatim — the body inside
a brace group is **not** internally reformatted by `shfmt`. This is an implementation trade-off:
safely unescaping, formatting, and re-escaping the contents without disrupting Snakemake's
variable interpolation introduces significant parser complexity, so opaque masking is used for
simplicity and safety.

If you need `shfmt` to format the body of a brace group, wrap it in `# fmt: off` / `# fmt: on`
and format that section manually.

#### Heredoc handling

`snakefmt` masks heredoc bodies before passing shell code to `shfmt`, and restores them afterwards. This means:

- **Heredoc bodies are never reformatted** — `shfmt` does not reformat heredoc content, and neither does `snakefmt`.
- **Snakemake-style escape prefixes on the terminator are supported.** For example, a heredoc that ends with `\n!EOF!` instead of a bare `!EOF!` at column 0 is detected and handled correctly — no `# fmt: off` required.

```
shell:
    """
    python <<!EOF!
    \nif True:
        print("hello")
    \n!EOF!
    """
```

Standard heredoc forms (`<<EOF`, `<<-EOF`, `<<'EOF'`) are also supported and the terminator placement requirement (column 0 for `<<EOF`, leading tabs only for `<<-EOF`) is preserved after formatting.

#### Invalid shell

If `shfmt` cannot parse the shell body, `snakefmt` raises an `InvalidShell` error rather than silently leaving the block unformatted.
To work around genuinely invalid shell, either:

- Disable shell formatting for the whole run with `-F` / `--no-format-shell`, or
- Wrap the rule in `# fmt: off` / `# fmt: on` directives (see below) to opt that block out.

</details>

### Format Directives

`snakefmt` supports comment directives to control formatting behaviour for specific regions of code.
Directives should appear as standalone comment lines, an inline occurrence (e.g. `input:  # fmt: off`) is treated as a plain comment and has no effect.
All directives are scope-local: only the region they select is affected, while code before and after follows normal `snakefmt` formatting and spacing rules (equivalent to replacing the directive with a plain comment line).

#### `# fmt: off` / `# fmt: on`

Disables all formatting for the region between the two directives.
Both directives *must* appear at the same indentation level; a `# fmt: on` at a deeper indent than the matching `# fmt: off` has no effect.

```python
rule a:
    input:
        "a.txt",


# fmt: off
rule b:
  input: "b.txt"
  output:
          "c.txt"
# fmt: on


rule c:
    input:
        "d.txt",
```

> **Note:** inside `run:` blocks and other Python contexts, `# fmt: off` / `# fmt: on` is passed through to [Black][black], which handles it natively.

<details>
<summary>Additional directives: <code># fmt: off[sort]</code>, <code># fmt: off[next]</code>, <code># fmt: skip</code></summary>

#### `# fmt: off[sort]`

Disables directive sorting for the enclosed region while still applying all other formatting.
Directives between `# fmt: off[sort]` and `# fmt: on[sort]` are kept in their original order.
A plain `# fmt: on` also closes a `# fmt: off[sort]` region.

```python
# fmt: off[sort]
rule keep_my_order:
    output:
        "result.txt",
    input:
        "source.txt",
    shell:
        "cp {input} {output}"
# fmt: on[sort]
```

#### `# fmt: off[next]`

Disables formatting for the single next Snakemake keyword block (e.g. `rule`, `checkpoint`, `use rule`).
Only that block is left unformatted; all subsequent blocks are formatted normally.

```python
rule formatted:
    input:
        "a.txt",
    output:
        "b.txt",


# fmt: off[next]
rule unformatted:
  input: "a.txt"
  output: "b.txt"


rule also_formatted:
    input:
        "a.txt",
```

#### `# fmt: skip`

`# fmt: skip` preserves a single line exactly as written, without any formatting (see [Black's documentation][black-skip] for details).

> **Note:** `# fmt: skip` is not yet supported within Snakemake rule blocks.
> It currently applies only to plain Python lines outside of rules, checkpoints, and similar Snakemake constructs.

</details>

### Configuration

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

[`pyproject.toml`][pyproject]

```toml
[tool.snakefmt]
line_length = 90
include = '\.smk$|^Snakefile|\.py$'
sort_directives = true   # sort rule directives into a consistent order (default: true)
format_shell = true      # format shell: blocks with shfmt (default: true)

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
    rev: v1.1.0 # Replace by any tag/version ≥v0.6.0 : https://github.com/snakemake/snakefmt/releases
    hooks:
      - id: snakefmt
```

Then [install pre-commit](https://pre-commit.com/#installation) and initialize the pre-commit hooks by running `pre-commit install` (Note you need to run this step once per clone of your repository). Additional pre-commit hooks can be found [here](https://pre-commit.com/hooks.html).

### GitHub Actions

[GitHub Actions](https://github.com/features/actions) in combination with [super-linter](https://github.com/github/super-linter) allows you to automatically run `snakefmt` on all Snakefiles in your repository e.g. whenever you push a new commit.

<details>
<summary>Show GitHub Actions workflow configuration</summary>

Create `.github/workflows/linter.yml` in your repository:

```yaml
---
name: Lint

on: # yamllint disable-line rule:truthy
  push: null
  pull_request: null

permissions: {}

jobs:
  build:
    name: Lint
    runs-on: ubuntu-latest

    permissions:
      contents: read
      packages: read
      # To report GitHub Actions status checks
      statuses: write
    steps:
      - name: Checkout code
        uses: actions/checkout@v5
        with:
          # super-linter needs the full git history to get the
          # list of files that changed across commits
          fetch-depth: 0
          persist-credentials: false

      - name: Lint Code Base
        uses: super-linter/super-linter@v8.2.1
        env:
          VALIDATE_ALL_CODEBASE: false
          DEFAULT_BRANCH: main
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}

          VALIDATE_SNAKEMAKE_SNAKEFMT: true
```

Additional configuration parameters can be specified by creating `.github/linters/.snakefmt.toml`:

```toml
[tool.black]
skip_string_normalization = true
```

</details>

For more information check the `super-linter` readme.

## Plug Us

If you can't get enough of badges, then feel free to show others you're using `snakefmt`
in your project.

[![Code style: snakefmt](https://img.shields.io/badge/code%20style-snakefmt-000000.svg)](https://github.com/snakemake/snakefmt)

<details>
<summary>Copy badge markup</summary>

### Markdown

```md
[![Code style: snakefmt](https://img.shields.io/badge/code%20style-snakefmt-000000.svg)](https://github.com/snakemake/snakefmt)
```

### ReStructuredText

```rst
.. image:: https://img.shields.io/badge/code%20style-snakefmt-000000.svg
    :target: https://github.com/snakemake/snakefmt
```

</details>

## Changes

See [`CHANGELOG.md`][changes].

## Contributing

See [CONTRIBUTING.md][contributing].

## Cite

[![DOI][doi-shield]][doi]

<details>
<summary>BibTeX</summary>

```bibtex
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

</details>


[snakemake]: https://snakemake.readthedocs.io/
[black]: https://black.readthedocs.io/en/stable/
[black-config]: https://github.com/psf/black#pyprojecttoml
[black-skip]: https://black.readthedocs.io/en/stable/usage_and_configuration/the_basics.html#ignoring-sections
[pyproject]: https://github.com/snakemake/snakefmt/blob/master/pyproject.toml
[contributing]: CONTRIBUTING.md
[changes]: CHANGELOG.md
[doi-shield]: https://img.shields.io/badge/DOI-10.12688%2Ff1000research.29032.2-brightgreen.svg
[doi]: https://doi.org/10.12688/f1000research.29032.2
