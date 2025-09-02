PROJECT = snakefmt
COVG_REPORT = htmlcov/index.html
OS := $(shell uname -s)
VERSION := $(shell uv version --short)
BOLD := $(shell tput bold)
NORMAL := $(shell tput sgr0)
# MAIN #########################################################################

.PHONY: all
all: install

# DEPENDENCIES #################################################################
.PHONY: install
install:
	uv sync

.PHONY: install-ci
install-ci:
	uv sync --frozen
	uv run snakefmt --version

# TIDY #################################################################
.PHONY: fmt
fmt:
	uv run isort .
	uv run black .

.PHONY: lint
lint:
	uv run flake8 . --extend-exclude .venv

.PHONY: check-fmt
check-fmt:
	uv run isort --check-only .
	uv run black --check .

# TEST ########################################################################
.PHONY: test
test:
	uv run pytest tests/ $(ARGS)

.PHONY: coverage
coverage:
	uv run pytest --cov-report term --cov-report html --cov=$(PROJECT) --cov-branch tests/
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
	uv build

# TAG ########################################################################
# prints out the commands to run to tag the release and push it
.PHONY: tag
tag:
	@echo "Run $(BOLD)git tag -a $(VERSION) -m <message>$(NORMAL) to tag the release"
	@echo "Then run $(BOLD)git push upstream $(VERSION)$(NORMAL) to push the tag"
