" Author: Brice Letcher
" Requires: Vim Ver7.0+
" Version:  1.0
"
" Documentation:
"   This plugin formats Snakemake files.
"   It is heavily inspired by black's vim plugin for Python: https://github.com/psf/black/blob/master/plugin/black.vim. All credit to its author Łukasz Langa.
"
" History:
"  1.0:
"    - initial version

func! __Set_SNAKEFMT_MISSING(message)
    command! Snakefmt echom a:message
    command! SnakefmtVersion echom a:message
endfunc
    
if v:version < 700 || !has('python3')
    __Set_SNAKEFMT_MISSING("The snakemake.vim plugin requires vim7.0+ with Python 3.6 support.")
    finish
endif

if exists("g:load_snakefmt")
   finish
endif

python3 << EndPython3
import sys
import vim
import time
from io import StringIO

try:
    from snakefmt import __version__ as snakefmt_version
    from snakefmt.snakefmt import read_snakefmt_config, DEFAULT_LINE_LENGTH
    from snakefmt.formatter import Formatter
    from snakefmt.parser.parser import Snakefile
except ModuleNotFoundError:
    error_message="snakefmt not found. Is snakefmt installed?"
    def Snakefmt():
        print(error_message)
    def SnakefmtVersion():
        print(error_message)
else:
    from black import find_pyproject_toml

    def Snakefmt():
      start = time.time()
      pyproject_toml: Optional[str] = find_pyproject_toml(vim.eval("fnamemodify(getcwd(), ':t')"))
      config = {"line_length": DEFAULT_LINE_LENGTH}
      config.update(read_snakefmt_config(pyproject_toml))

      buffer_str = '\n'.join(vim.current.buffer) + '\n'
      try:
        snakefile = Snakefile(StringIO(buffer_str))
        formatter = Formatter(snakefile, line_length=config["line_length"], black_config_file=pyproject_toml)
        new_buffer_str = formatter.get_formatted()
      except Exception as exc:
        print(exc)
      else:
        current_buffer = vim.current.window.buffer
        cursors = []
        for i, tabpage in enumerate(vim.tabpages):
          if tabpage.valid:
            for j, window in enumerate(tabpage.windows):
              if window.valid and window.buffer == current_buffer:
                cursors.append((i, j, window.cursor))
        vim.current.buffer[:] = new_buffer_str.split('\n')[:-1]
        for i, j, cursor in cursors:
          window = vim.tabpages[i].windows[j]
          try:
            window.cursor = cursor
          except vim.error:
            window.cursor = (len(window.buffer), 0)
        print(f'Reformatted with snakefmt in {time.time() - start:.4f}s.')

    def SnakefmtVersion():
      print(f'snakefmt version {snakefmt_version} on Python {sys.version}.')

EndPython3

let g:load_snakefmt = "py1.0"

command! Snakefmt :py3 Snakefmt()
command! SnakefmtVersion :py3 SnakefmtVersion()
