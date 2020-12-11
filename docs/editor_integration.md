# Editor Integration

If your favourite editor is not listed here, we would love to receive a PR with how to
include it.

**Unless otherwise specified, all instructions assume you have `snakefmt` installed
already.**

[TOC]: #

# Table of Contents
- [PyCharm/JetBrains IDEA](#pycharmjetbrains-idea)
- [Visual Studio Code](#visual-studio-code)
- [Vim](#Vim)


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

## Vim

Credit: plugin inspired by
[black](https://github.com/psf/black/blob/master/plugin/black.vim)

1. Install the plugin.

    Recommended way is via a plugin manager, eg [vim-plug](https://github.com/junegunn/vim-plug):

    ```
    Plug 'snakemake/snakefmt' 
    ```

    or [Vundle](https://github.com/VundleVim/Vundle.vim):

    ```
    Plugin 'snakemake/snakefmt'
    ```

2. That's it! Run `:Snakefmt` to format a buffer, and `:SnakefmtVersion` for version info.

    If you do not run Vim 7.0+ built with Python3.6+ support, or you have not installed `snakefmt`, those commands will complain.

3. If you want to format your file automatically when saving it, write this in your vimrc:

    ```
    au BufNewFile,BufRead Snakefile,*.smk set filetype=snakemake
    au FileType snakemake autocmd BufWritePre <buffer> execute ':Snakefmt'
    ```

4. If you additionally want syntax highlighting on your snakemake files, install snakemake's [syntax highlighter](https://github.com/snakemake/snakemake/tree/master/misc/vim)!

### Troubleshooting

Under certain circumstances, import errors can occur when using a virtual environment due to _Black_ dependency imports. See the [_Black_ Vim integration docs](https://black.readthedocs.io/en/stable/editor_integration.html#vim) for more details and a potential solution.
