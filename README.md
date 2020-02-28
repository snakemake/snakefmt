The goal of this repository is to provide formatting for [Snakemake][snakemake] akin to that of [Black][black].

It is extremely new and under active development. When it is ready for use, we will update
the documentation accordingly.

## Contributing

We welcome contributions to `snakefmt`. We outline a [recommended development setup](#recommended-development-workflow) and
workflow below. Of course, if you have your own system you would prefer to follow, that
is fine. Regardless of the development process you use, please ensure the code you have
changed is formatted with `black` as per the specifications in [`pyproject.toml`][pyproject].

### Recommended development workflow

Firstly, fork this repository. Then run the following.

```bash
# clone your fork locally
git clone https://github.com/<username>/snakefmt.git
cd snakefmt
# create and install a poetry environment - https://python-poetry.org
poetry install
# activate the project environment
poetry shell
# setup the pre-commit hook that will format the project with black
pre-commit install
```

You should be all set to go now!

[snakemake]: https://snakemake.readthedocs.io/
[black]: https://black.readthedocs.io/en/stable/
[pyproject]: https://github.com/mbhall88/snakefmt/blob/master/pyproject.toml
[poetry]: https://python-poetry.org