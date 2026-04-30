# snakefmt.nvim

![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/snakemake/snakefmt/ci.yaml?branch=master)
[![codecov](https://codecov.io/gh/snakemake/snakefmt/branch/master/graph/badge.svg)](https://codecov.io/gh/snakemake/snakefmt)
[![PyPI](https://img.shields.io/pypi/v/snakefmt)](https://pypi.org/project/snakefmt/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Neovim plugin for [snakefmt](https://github.com/snakemake/snakefmt), the uncompromising Snakemake code formatter.

## Features

- Fast formatting using `vim.system`.
- Fallback to `uvx snakefmt` if `snakefmt` is not in PATH.
- Configurable line length.
- Auto-format on save.

## Installation

### [lazy.nvim](https://github.com/folke/lazy.nvim)

```lua
{
  "snakemake/snakefmt",
  ft = { "snakemake", "python" }, -- optional: only load for these filetypes
  config = function()
    require("snakefmt").setup({
      -- your configuration here
    })
  end,
}
```

### [packer.nvim](https://github.com/wbthomason/packer.nvim)

```lua
use {
  "snakemake/snakefmt",
  config = function()
    require("snakefmt").setup()
  end
}
```

## Configuration

Default options:

```lua
require("snakefmt").setup({
  auto_format = false,    -- Set to true to enable auto-format on save
  line_length = nil,      -- Overrides default snakefmt line length if set
  bin_path = nil,         -- Specific path to snakefmt binary
  uvx_fallback = true,    -- Fallback to 'uvx snakefmt' if binary not found
})
```

## Usage

### Commands

- `:Snakefmt`: Format the current buffer.
- `:SnakefmtInfo`: Show execution info (binary path used).

### Auto-format on save

You can enable auto-format on save globally in the setup:

```lua
require("snakefmt").setup({
  auto_format = true,
})
```

This will automatically format `*.smk` and `Snakefile` files on save.

## Requirements

- Neovim >= 0.10.0
- `snakefmt` installed in PATH, OR `uv` installed (for fallback).
