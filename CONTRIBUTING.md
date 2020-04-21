# Contributing

We welcome contributions to `snakefmt`. We outline a
[recommended development setup](#recommended-development-workflow) and workflow below.
Of course, if you have your own system you would prefer to follow, that is fine.
Regardless of the development process you use, please ensure the code you have changed
is formatted with `black` as per the specifications in [`pyproject.toml`][pyproject] and
there are no `flake8` warnings in accordance with [`.flake8`][flake8].

### Recommended development workflow

Firstly, fork this repository. Then run the following.

```shell
# clone your fork locally
git clone https://github.com/<username>/snakefmt.git
cd snakefmt
# create and install a poetry environment - https://python-poetry.org
poetry install
# activate the project environment
poetry shell
# setup the pre-commit hook that will format the project with black
pre-commit install
# run tests BEFORE committing
pytest
```

You should be all set to go now!


[pyproject]: https://github.com/snakemake/snakefmt/blob/master/pyproject.toml
[flake8]: https://github.com/snakemake/snakefmt/blob/master/.flake8

