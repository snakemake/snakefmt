import tokenize
from typing import Callable

from snakefmt.parser.blocks import Block, python_subautomata
from snakefmt.parser.grammar import global_snakemake_subautomata
from snakefmt.parser.tokens import TokenIterator


class Snakefile(Block):
    """The global scope of a Snakemake file.

    Holds `body_blocks` only, no `head_lines` nor `tail_noncoding`.
    All blocks in `body_blocks` are in the same deindent level as the
    `Snakefile` itself, so `tail_noncoding` is always updated to the last
    body_block. It is also reused for the bodies of control-flow blocks
    (`if`/`for`/`with`/`match case`), which share the global subautomata.
    """

    __slots__ = ()

    subautomata = {**python_subautomata, **global_snakemake_subautomata}

    def consume(self, tokens):
        self.body_blocks = self.consume_subblocks(tokens)

    def compilation(self):
        raise NotImplementedError

    @classmethod
    def parse(cls, source: str | Callable[[], str], name: str = "<string>"):
        if isinstance(source, str):
            tokens = tokenize.generate_tokens(
                iter(source.splitlines(keepends=True)).__next__
            )
        else:
            tokens = tokenize.generate_tokens(source)
        return cls(0, TokenIterator(name, tokens), [])
