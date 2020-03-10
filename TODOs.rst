Parsing
=========

[] have code distinguish parsing (and syntax validation) from formatting and compiling. parsing needs to run successfully before either.

[] Register run keyword as processed

[] Whitespace at indent level 0: add newlines

Grammar
==========

[x] support for python code inside run directive

[x] only allow indented line continuations for parameters if they are string tokens.

Errors/exceptions
===================

[x] All syntax error related exceptions should state which line they occur on

Testing
==========

[] Test calls are being made to black formatting

[] Test suite where expect snakefmt to run fine

Code practice
=================

[] Absolute imports (PEP8)
