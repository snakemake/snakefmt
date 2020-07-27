PROJECT = snakefmt
COVG_REPORT = htmlcov/index.html
OS := $(shell uname -s)
VERSION := $(shell poetry version | grep -P '(?P<version>\d.\d.\d)' --only-matching)
BOLD := $(shell tput bold)
NORMAL := $(shell tput sgr0)
# MAIN #########################################################################

.PHONY: all
all: install

# DEPENDENCIES #################################################################
.PHONY: install
install:
	poetry install

.PHONY: install-ci
install-ci:
	python -m pip install --upgrade pip
	python -m pip install poetry
	poetry install --no-interaction

# TIDY #################################################################
.PHONY: fmt
fmt:
	poetry run isort .
	poetry run black .

.PHONY: lint
lint:
	poetry run flake8 .

.PHONY: check-fmt
check-fmt:
	poetry run isort --check-only .
	poetry run black --check .

# TEST ########################################################################
.PHONY: test
test:
	poetry run pytest tests/

.PHONY: coverage
coverage:
	poetry run pytest --cov-report term --cov-report html --cov=$(PROJECT) --cov-branch tests/
ifeq ($(OS), Linux)
	xdg-open $(COVG_REPORT)
else ifeq ($(OS), Darwin)
	open $(COVG_REPORT)
else
	echo "ERROR: Unknown OS detected - $OS"
endif

# PRECOMMIT ########################################################################
# runs format, lint and test
.PHONY: precommit
precommit: fmt lint test

# BUILD ########################################################################
.PHONY: build
build:
	poetry build

# TAG ########################################################################
# prints out the commands to run to tag the release and push it
.PHONY: tag
tag:
	@echo "Run $(BOLD)git tag -a $(VERSION) -m <message>$(NORMAL) to tag the release"
	@echo "Then run $(BOLD)git push upstream $(VERSION)$(NORMAL) to push the tag"