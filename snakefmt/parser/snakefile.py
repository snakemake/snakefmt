import tokenize
from typing import Callable

from snakefmt.exceptions import UnsupportedSyntax
from snakefmt.parser.blocks import Block, ColonBlock
from snakefmt.parser.grammar import global_snakemake_subautomata, init_block_register
from snakefmt.parser.tokens import TokenIterator, splitlines


class ScopeBodyBlock(ColonBlock):
    """A colon block whose body is ordinary global scope.

    Snakemake dispatches keywords at every line start regardless of indentation
    (`snakemake.parser.Python.python`), so `def`/`class` bodies and control-flow
    bodies are parsed with the global subautomata, exactly like a Snakefile.
    """

    def consume_body(self, tokens):
        blocks = Snakefile(self.deindent_level + 1, tokens, []).body_blocks
        self.body_blocks.extend(blocks)


python_subautomata, _register = init_block_register()


def _register_scope(keyword: str, **kwargs):
    """A `ScopeBodyBlock` named after `keyword` (so `.keyword` is correct)."""
    block = type(keyword.capitalize(), (ScopeBodyBlock,), kwargs)
    return _register(keyword)(block)


for keyword in ("if elif else " "for while " "try except finally " "with").split():
    _register_scope(keyword)

for keyword in ("def", "class"):
    _register_scope(keyword, allow_decorate=True)
"""Blocks starting with `def`, `class` or `async`, with heading decorators (`@` lines).
Its body is global scope (snakemake keywords may appear there).
"""


@_register()
class Match(ColonBlock):
    subautomata, _register = init_block_register()

    @_register()
    class Case(ScopeBodyBlock): ...

    def consume_body(self, tokens):
        blocks = self.consume_subblocks(tokens, ender_subblock=True)
        if any(not isinstance(i, self.Case) for i in blocks):
            raise UnsupportedSyntax(
                f"Unexpected content in {self.keyword} block: "
                f"only `Case` keyword is allowed, but got {blocks}"
            )
        self.body_blocks = blocks


_register_scope("async", allow_decorate=True)
"""Blocks starting with `async`,
it is rediculous to have snakemake directives in `async`,
but just in case, let them go.
"""


class Snakefile(Block):
    """The global scope of a Snakemake file.

    Holds `body_blocks` only, no `head_lines` nor `tail_noncoding`.
    All blocks in `body_blocks` are in the same deindent level as the
    `Snakefile` itself, so `tail_noncoding` is always updated to the last
    body_block. It is also reused for the bodies of control-flow blocks
    (`if`/`for`/`with`/`match case`) and callable blocks (`def`/`class`),
    which share the global subautomata.
    """

    __slots__ = ()

    subautomata = python_subautomata | global_snakemake_subautomata

    def consume(self, tokens):
        self.body_blocks = self.consume_subblocks(tokens)

    @classmethod
    def parse(cls, source: str | Callable[[], str], name: str = "<string>"):
        if isinstance(source, str):
            tokens = tokenize.generate_tokens(splitlines(source).__next__)
        else:
            tokens = tokenize.generate_tokens(source)
        return cls(0, TokenIterator(name, tokens), [])
