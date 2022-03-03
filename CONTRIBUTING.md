# Contributing

We welcome contributions to `snakefmt`. We outline a
[recommended development setup](#recommended-development-workflow) and workflow below.
Of course, if you have your own system you would prefer to follow, that is fine.
Regardless of the development process you use, please ensure the code you have changed
is formatted with `black` and `isort` as per the specifications in [`pyproject.toml`][pyproject]
and there are no `flake8` warnings in accordance with [`.flake8`][flake8].

### Recommended development workflow

Firstly, fork this repository. If you are using `poetry` most of the standard workflow
options are handled with rules in the `Makefile`. An example of how to install the
project and run some common routines is below.

```shell
# clone your fork locally
git clone https://github.com/<username>/snakefmt.git
cd snakefmt
# create and install a poetry environment - https://python-poetry.org
make install
# format all files
make fmt
# lint all files
make lint
# test
make test
# all three in one
make precommit
```

You should be all set to go now!


[pyproject]: https://github.com/snakemake/snakefmt/blob/master/pyproject.toml
[flake8]: https://github.com/snakemake/snakefmt/blob/master/.flake8


### Pull requests

Any changes to snakefmt should be provided as pull requests via Github.
Importantly, the pull request title has to follow the [conventional commits specification](https://www.conventionalcommits.org).
If the pull requests consists of a single commit, the commit message of that commit has to follow the [conventional commits specification](https://www.conventionalcommits.org) as well.
