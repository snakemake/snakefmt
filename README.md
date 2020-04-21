[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

This repository provides formatting for [Snakemake][snakemake] files. It follows the design and specifications of [Black][black].

## Install

``` bash
git clone https://github.com/snakemake/snakefmt
pip install poetry
cd snakefmt && poetry install
poetry shell
```

## Usage

```
Usage: snakefmt [OPTIONS] [SRC]...

  The uncompromising Snakemake code formatter.

Options:
  -l, --line-length INTEGER  [default: 88]
  --include TEXT             A regular expression that matches files and
							 directories that should be included on recursive
							 searches.  An empty value means all files are
							 included regardless of the name.  Use forward
							 slashes for directories on all platforms
							 (Windows, too).  Exclusions are calculated first,
							 inclusions later.  [default: (\.smk$|^Snakefile)]
  --exclude TEXT             A regular expression that matches files and
							 directories that should be excluded on recursive
							 searches.  An empty value means no paths are
							 excluded. Use forward slashes for directories on
							 all platforms (Windows, too). Exclusions are
							 calculated first, inclusions later.  [default: (\
							 .snakemake|\.eggs|\.git|\.hg|\.mypy_cache|\.nox|\
							 .tox|\.venv|\.svn|_build|buck-out|build|dist)]
  -h, --help                 Show this message and exit.
  -V, --version              Show the version and exit.
  -v, --verbose              Turns on debug-level logging.
```

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

Example File
-------------

Input

```python
SAMPLES = ["s1", "s2"]
CONDITIONS = ["a", "b"]

if True:
	rule can_be_inside_python_code:
		input: "parameters", "get_indented"
		threads: 4 # Numeric params stay unindented
		params: key_val = "PEP8_formatted"
		run:

					print("weirdly_spaced_string_gets_respaced")

rule gets_separated_by_two_newlines:
	input:
		files=expand("long/string/to/data/files/gets_broken_by_black/{sample}.{condition}",sample=SAMPLES, condition=CONDITIONS)
```


Output

```python
SAMPLES=["s1","s2"]
CONDITIONS=["a","b"]

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


rule gets_separated_by_two_newlines:
	input:
		files=expand(
		"long/string/to/data/files/gets_broken_by_black/{sample}.{condition}",
		sample=SAMPLES,
		condition=CONDITIONS,
		),
```
    

## Contributing

Please refer to [CONTRIBUTING.md][contributing].


[snakemake]: https://snakemake.readthedocs.io/
[black]: https://black.readthedocs.io/en/stable/
[PEP8]: https://www.python.org/dev/peps/pep-0008/
[pyproject]: https://github.com/snakemake/snakefmt/blob/master/pyproject.toml
[poetry]: https://python-poetry.org
[contributing]: CONTRIBUTING.md
