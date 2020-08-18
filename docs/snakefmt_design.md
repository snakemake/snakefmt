## Syntax

`snakefmt`'s parser will spot syntax errors in your snakefiles:

* Unrecognised keywords
* Duplicate keywords
* Invalid parameters
* Invalid python code

But `snakefmt` not complaining does not guarantee your file is entirely error-free.

## Formatting

Python code is `black`ed.

Snakemake-specific syntax is formatted following the same principles: see [PEP8][PEP8].

[PEP8]: https://www.python.org/dev/peps/pep-0008/
