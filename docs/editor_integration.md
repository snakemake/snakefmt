# Editor Integration

If your favourite editor is not listed here, we would love to receive a PR with how to
include it.

**Unless otherwise specified, all instructions assume you have `snakefmt` installed
already.**

[TOC]: #

# Table of Contents
- [PyCharm/JetBrains IDEA](#pycharmjetbrains-idea)
- [Visual Studio Code](#visual-studio-code)
- [Vim / Neovim](#vim--neovim)
- [emacs](#emacs)


## PyCharm/JetBrains IDEA

1. Locate the path to your `snakefmt` executable.

```sh
# linux and macOS
$ which snakefmt
/usr/local/bin/snakefmt  # just an example

# windows
$ where snakefmt
%LocalAppData%\Programs\Python\Python36-32\Scripts\snakefmt.exe  # just an example
```

2. Open External tools in PyCharm/IntelliJ IDEA

- On macOS: `PyCharm -> Preferences -> Tools -> External Tools`

- On Windows / Linux / BSD: `File -> Settings -> Tools -> External Tools`

3. Click the `+` icon to add a new external tool with the following values:

   - Name: Snakefmt
   - Description: The uncompromising Snakemake code formatter
   - Program: result of `which/where snakefmt` from step 1
   - Arguments: `"$FilePath$"`

4. Format the currently opened file by selecting `Tools -> External Tools -> Snakefmt`.

   - Alternatively, you can set a keyboard shortcut by navigating to
     `Preferences/Settings -> Keymap -> External Tools -> External Tools - Snakefmt`. We
     use <kbd>Alt</kbd>+<kbd>s</kbd>

5. Optionally, run `snakefmt` on every file save:

   1. Make sure you have the
      [File Watchers](https://plugins.jetbrains.com/plugin/7177-file-watchers) plugin
      installed.
   2. Go to `Preferences or Settings -> Tools -> File Watchers` and click `+` to add a
      new watcher:
      - Name: Snakefmt
      - File type: Python
      - Scope: Project Files
      - Program: result of `which/where snakefmt` from step 1
      - Arguments: `$FilePath$`
      - Output paths to refresh: `$FilePath$`
      - Working directory: `$ProjectFileDir$`

   - Uncheck "Auto-save edited files to trigger the watcher" in Advanced Options

## Visual Studio Code

1. Install the extension within [Visual Studio (VS) Code](https://code.visualstudio.com/) by visiting the [Snakefmt extension](https://marketplace.visualstudio.com/items?itemName=tfehlmann.snakefmt) page and following the instructions at the top of the page.

2. Follow the directions under the extension's [Details](https://marketplace.visualstudio.com/items?itemName=tfehlmann.snakefmt#features) page. Pay attention in particular to the [Requirements](https://marketplace.visualstudio.com/items?itemName=tfehlmann.snakefmt#requirements) section to provide a path to your `snakefmt` executable (if it isn't already in your `PATH` environment variable).

3. See VS Code's documentation on [Formatting](https://code.visualstudio.com/docs/editor/codebasics#_formatting) for more instructions on how to apply formatting within the IDE.

## Vim / Neovim

### Neovim (Recommended)

A modern Lua-based plugin for Neovim 0.10+ that provides asynchronous, non-blocking formatting.

#### Features
- Fast formatting using `vim.system`.
- Automatic fallback to `uv run --with snakefmt snakefmt` if `snakefmt` is not in your environment.
- Configurable line length and auto-format on save.

#### Installation (with [lazy.nvim](https://github.com/folke/lazy.nvim))

```lua
{
  "snakemake/snakefmt",
  ft = { "snakemake" },
  config = function()
    require("snakefmt").setup({
      -- auto_format = true, -- uncomment to enable auto-format on save
    })
  end,
}
```

#### Usage
- `:Snakefmt`: Format the current buffer.
- `:SnakefmtInfo`: Show which `snakefmt` binary is being used.

---

### Vim (Legacy)

Credit: plugin inspired by [black](https://github.com/psf/black/blob/master/plugin/black.vim)

1. Install the plugin using a manager like [vim-plug](https://github.com/junegunn/vim-plug):

    ```vim
    Plug 'snakemake/snakefmt'
    ```

2. Run `:Snakefmt` to format a buffer, and `:SnakefmtVersion` for version info.
   Note: Requires Vim 7.0+ with Python 3.6+ support.

3. To format automatically on save, add to your `vimrc`:

    ```vim
    au BufNewFile,BufRead Snakefile,*.smk set filetype=snakemake
    au FileType snakemake autocmd BufWritePre <buffer> execute ':Snakefmt'
    ```

### Syntax Highlighting

For syntax highlighting in both Vim and Neovim, install the [Snakemake syntax highlighter](https://github.com/snakemake/snakemake/tree/master/misc/vim).


## emacs

The [`format-all` package](https://github.com/lassik/emacs-format-all-the-code) supports use of `snakefmt` out of the box provided `snakefmt` is available on the `exec-path`; it should suffice to have `snakefmt` available on your `PATH`.

`snakefmt` can be invoked in a buffer using `format-all` in the usual way with `format-all-buffer`, and also by adding a hook to your dotfile to enable the `format-all-mode` minor mode. If you are using [`snakemake-mode`](https://git.kyleam.com/snakemake-mode/about/) already, you can do this with:
```elisp
(add-hook `snakemake-mode-hook #`format-all-mode)
```

See the [`format-all` repo](https://github.com/lassik/emacs-format-all-the-code) for more documentation.
