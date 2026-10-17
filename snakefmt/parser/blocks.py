import tokenize
from abc import ABC, abstractmethod
from collections import OrderedDict
from tokenize import TokenInfo
from typing import Iterator, Mapping, NamedTuple, Optional, TypeVar

from snakefmt.exceptions import UnsupportedSyntax
from snakefmt.parser.tokens import (
    LogicalLine,
    TokenIterator,
    extract_line_indent,
    is_op,
    tokens2linestrs,
)


class Block(ABC):
    """
    A block can be:
        a continuous python code of lines with the same indentation level.
            Also include functions, classes and decoraters (`@` lines)
        a single block identifed by keywords in
                if/elif/else / for/while / try/except/finally / with
            and all the code under it, until the next block
              of the same or lower indent level.
        a snakemake keyword block (rule, module, config, etc.)
            and all the code under it, until the next block
              of the same or lower indent level.
            (snakemake keywords should NEVER in functions or classes)
        comments between blocks
            (exclude the comment right before the indenting keyword,
              which is considered part of the block)

    Starting of blocks (file or new indent):
        the space and comments until the first indenting keyword
          are considered a block of their own.

    All other spaces are considered part of the previous block's trailing empty lines.

    Comment belongness:
        Only comments with neither empty lines between/after the next block
          nor different indent levels are considered part of the same block.
        ```python
        sth # block 1
        # comment 1 -> block 1

        # comment 2 -> block 1

        # comment 3 -> block 2
        def func(): # block 2
            pass # block 2.1
            # comment 4 -> block 2.1
        # comment 5 -> block 2

        rule example: # block 3
            input: "data.txt" # block 3.1 and 3.1.1
            # comment 6 -> block 3.1
            output: # block 3.2
                "result.txt" # block 3.2.1
                # comment 7 -> block 3.2.1
            # comment 8 -> block 3.3
        ```

    Indent of comments:
        determined by the following real code line and previous indents.

        Durning parsing tokens, when a comment token is encountered,
        its effective indent level is not directly knowable.

        principles:
        ```python
        follow_indent = indent of the following real code line
        if EOF:
            follow_indent = 0
        rule 1 (always):
            indent of comments >= follow_indent
        rule 2 (if follow_indent < self.indents[-1]):
            indent of comments = epsilon + max(
                i for i in self.indents if i <= comment_indent
            )
        ```
    """

    __slots__ = ("deindent_level", "head_lines", "body_blocks", "tail_noncoding")
    subautomata: Mapping[str, "type[ColonBlock]"] = {}
    deprecated: Mapping[str, str] = {}

    def __init__(
        self,
        deindent_level: int,
        tokens: TokenIterator,
        lines: list[LogicalLine] | None = None,
    ):
        self.deindent_level = deindent_level
        self.head_lines = [] if lines is None else lines
        self.body_blocks: list[Block] = []
        self.tail_noncoding: list[TokenInfo] = []
        self.consume(tokens)

    def extend_tail_noncoding(self, tokens: list[TokenInfo]):
        self.tail_noncoding.extend(tokens)

    @abstractmethod
    def consume(self, tokens: TokenIterator) -> None:
        """extract blocks, logical lines and comments from tokens.
        Should return when the block is ended by DEDENT or ENDMARKER,
        and push back them as well as the comments.
        """

    def recognize(self, token: TokenInfo):
        """Whether the block can be recognized by the first token of its head lines"""
        if token.type == tokenize.NAME:
            if token.string in self.subautomata:
                return self.subautomata[token.string]
            if token.string in self.deprecated:
                raise UnsupportedSyntax(
                    f"Keyword {token.string!r} is deprecated, "
                    f"{self.deprecated[token.string]!r}."
                )

    def consume_subblocks(self, tokens: TokenIterator, ender_subblock=False):
        """Split all lines of same indent into plain Python blocks and indent blocks,
        until the end of file or DEDENT out.

        - select subautomata to consume indent blocks
        - denext_by_indent when DEDENT out

        Used in Snakefile and SnakemakeDirectiveBlock, to consume their body blocks.
        """
        deindent_level = self.deindent_level + int(ender_subblock)
        blocks: list[Block] = []

        plain_python_lines: list[LogicalLine] = []
        tail_noncoding: list[TokenInfo] = []
        indent_str = "[TBD]"

        def append_sub(block_type: type[ColonBlock], header_lines: list[LogicalLine]):
            if plain_python_lines:
                blocks.append(
                    PythonBlock(deindent_level, tokens, list(plain_python_lines))
                )
                plain_python_lines.clear()
            blocks.append(block_type(deindent_level, tokens, header_lines))

        while True:
            line = tokens.next_new_line()
            if line.deindelta > 0 and indent_str != "[TBD]":
                tokens.denext(*reversed(list(line.iter)))
                assert plain_python_lines, "Unexpected INDENT without any content"
                header_line = plain_python_lines.pop()
                append_sub(UnknownIndentBlock, [header_line])
                continue
            elif line.deindelta < 0:
                assert indent_str and indent_str != "[TBD]"
                tail_noncoding = tokens.denext_by_indent(line, indent_str, 1)
                break
            elif line.end.type == tokenize.ENDMARKER:
                plain_python_lines.append(
                    LogicalLine(line.head_noncoding, [], [], line.end)
                )
                blocks.append(PythonBlock(deindent_level, tokens, plain_python_lines))
                plain_python_lines = []
                break
            else:
                if indent_str == "[TBD]":
                    assert (
                        line.body
                    ), "Unexpected empty line at the beginning of a block"
                    indent_str = extract_line_indent(line.body[0].line)
                if block := self.recognize(line.body[0]):
                    append_sub(block, [line])
                elif line.body[0].string == "@":
                    headers = [line]
                    while True:
                        headers.append(tokens.next_new_line())
                        if block := self.recognize(headers[-1].body[0]):
                            break
                    append_sub(block, headers)
                else:
                    plain_python_lines.append(line)
        if plain_python_lines:
            blocks.append(PythonBlock(deindent_level, tokens, plain_python_lines))
        if tail_noncoding:
            assert blocks
            blocks[-1].extend_tail_noncoding(tail_noncoding)
        return blocks

    @property
    def start_token(self) -> TokenInfo | None:
        for line in self.head_lines:
            if line.body:
                return line.body[0]
        for block in self.body_blocks:
            token = block.start_token
            if token:
                return token
        return None

    @property
    def indent_str(self) -> str:
        "tell the raw indent of the block"
        assert self.start_token is not None, "start_token should be set after consume()"
        return self.start_token.line[: self.start_token.start[1]]

    @property
    def head_linestrs(self):
        for line in self.head_lines:
            yield from line.linestrs

    @property
    def full_linestrs(self):
        """return the code splited by lines, but should keep multiline-string
          or multiline-f-string complete,
        to make trimming and reformatting easier.

        Should and Only should be rewrite for pure python blocks.
        """
        yield from self.head_linestrs
        for block in self.body_blocks:
            yield from block.full_linestrs
        yield from tokens2linestrs(iter(self.tail_noncoding))

    def components(self) -> "Iterator[DocumentSymbol]":
        """
        - position := (file, line number, column number)
        - type := name / rule, input, output / function, class / etc.
            if not a name, then that's the definition of the name
                (should link blank names to here)
        - identifier := the identifier of the block,
                e.g. rule `a`, `input`, input `b`, etc.
            when iterating sub-blocks in rule, identifier should modified to
              reflect the parent block, e.g. `rules.a.input.b`
            (`b` may be difficult to identify,
              but at least we know the content of `input` block)
        - content := "self.raw()", e.g. `"data.txt"` for input `b` in rule `a`,
                     and the whole content of the block for rule `a`

        Idealy, it should recognize sth like:
            rules.a.input.b
        - enable `rules.a` to the position of `rule a:`
        - enable `~~~~~~~.input` to the position of `input:` of `rule a`
        - enable `~~~~~~~~~~~~~.b` to the position of `b=` in `input:` of `rule a`
        """
        for block in self.body_blocks:
            yield from block.components()

    @abstractmethod
    def compilation(self):
        """return pure python code compiled from the block,
        without snakemake keywords and comments"""


class DocumentSymbol(NamedTuple):
    name: str
    detail: str
    symbol_kind: str
    position_start: tuple[int, int]
    position_end: tuple[int, int]
    block: Block


class PythonBlock(Block):
    """Hold `head_lines` and `tail_noncoding`, no `body_blocks`"""

    def consume(self, tokens):
        "Do nothing, win"

    def compilation(self):
        raise NotImplementedError

    def components(self):
        yield from []


class ColonBlock(Block):
    """
    Hold `head_lines`, `body_blocks`, `tail_noncoding` for:
        "`subautomata` ...`:` [COMMENT]" <- headlines
            `line`                       <- body_blocks[0]
            [...]                        <- body_blocks[1:]
    or
        "`subautomata` ...`:` `inline`"  <- headlines
        body_blocks is empty
    """

    @classmethod
    def _keyword(cls):
        return cls.__name__.lower()

    @property
    def keyword(self) -> str:
        """Used such as `yield f"workflow.{self.keyword}("`"""
        return self._keyword()

    def split_colon_line(self):
        """Split the colon line into two parts:
        - lines before the colon
        - token iterator starting from the colon token (inclusive)
        """
        token_iter = TokenIterator(
            "", iter(self.colon_line.body + [self.colon_line.end])
        )
        last_line_tokens = []
        while True:
            component = token_iter.next_component()
            if len(component) == 1 and is_op(":", *component):
                break
            last_line_tokens.extend(component)
        (colon_token,) = component
        prior = tokens2linestrs(iter(last_line_tokens))
        prior[-1] = prior[-1][: colon_token.start[1]]
        token_iter.denext(colon_token)
        return prior, token_iter

    @property
    def colon_line(self):
        assert self.head_lines, "ColonBlock should have head lines"
        return self.head_lines[-1]

    def consume(self, tokens):
        """Consume tokens until the end of the block head line (the line with `:`)"""
        if self.colon_line.endswith_colon:
            self.consume_body(tokens)
        # else: single line indent such as `else: pass` or `except: pass`

    @abstractmethod
    def consume_body(self, tokens: TokenIterator) -> None:
        """Consume tokens until the end of the block body (the next DEDENT)
        The syntax will be validated by the subautomata, if any.
        """

    def recognises(self, token: TokenInfo):
        return token.type == tokenize.NAME and token.string == self.keyword


def init_block_register():
    T = TypeVar("T", bound=ColonBlock)

    def register_block(name: Optional[str] = None):
        def decorator(type_: type[T]) -> type[T]:
            keyword = name or type_._keyword()
            namespace[keyword] = type_
            return type_

        return decorator

    namespace: OrderedDict[str, type[ColonBlock]] = OrderedDict()
    return namespace, register_block


class ColonPythonBlock(ColonBlock):
    """Refused to consume body blocks.
    Treat the body as plain Python code, until the next DEDENT"""

    def consume_body(self, tokens):
        lines, tail_noncoding = tokens.next_block()
        codes = PythonBlock(self.deindent_level + 1, tokens, lines)
        codes.extend_tail_noncoding(tail_noncoding)
        self.body_blocks.append(codes)

    def compilation(self):
        raise NotImplementedError


class UnknownIndentBlock(ColonPythonBlock):
    """Although I cannot imadge why an INDENT occurs
    without the control of known colon keywords,
    but just in case, I will treat the indented content as plain Python.
    """


class NamedBlock(ColonBlock):
    __slots__ = ("name",)
    name: str

    def components(self):
        this_symbol = DocumentSymbol(
            name=self.name,
            detail="\n".join(i.rstrip() for i in self.head_linestrs).strip("\n"),
            symbol_kind=self._keyword(),
            position_start=self.colon_line.body[0].start,
            position_end=self.colon_line.body[-1].end,
            block=self,
        )
        yield this_symbol
