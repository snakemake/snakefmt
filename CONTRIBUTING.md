# Contributing

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
# run tests BEFORE commiting
pytest
```

We ask (but don't enforce) that you also run [`isort`][isort] and [`mypy`][mypy] before 
commiting any code. These tools should be installed with the develop dependencies by 
`poetry` automatically. The following commands will automatically use the default settings 
for this project.

```bash
isort -y
mypy .
```

You should be all set to go now!


[pyproject]: https://github.com/mbhall88/snakefmt/blob/master/pyproject.toml
[isort]: https://github.com/timothycrosley/isort
[mypy]: https://github.com/python/mypy