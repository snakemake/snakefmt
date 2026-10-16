import tokenize
from abc import ABC, abstractmethod
from tokenize import TokenInfo
from typing import Iterable, Iterator, Mapping, NamedTuple

from snakefmt.exceptions import (
    ColonError,
    InvalidParameter,
    InvalidParameterSyntax,
    NewlineError,
    NoParametersError,
    NotAnIdentifierError,
    TooManyParameters,
    UnsupportedSyntax,
)
from snakefmt.parser.tokens import (
    LogicalLine,
    TokenIterator,
    effective,
    extract_line_indent,
    is_op,
    line_nb,
    tokens2linestrs,
    validate_parameters,
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

        Used in GlobalBlock and SnakemakeDirectiveBlock, to consume their body blocks.
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
        if self.colon_line.end_op == ":":
            self.consume_body(tokens)
        # else: single line indent such as `else: pass` or `except: pass`

    @abstractmethod
    def consume_body(self, tokens: TokenIterator) -> None:
        """Consume tokens until the end of the block body (the next DEDENT)
        The syntax will be validated by the subautomata, if any.
        """

    def recognises(self, token: TokenInfo):
        return token.type == tokenize.NAME and token.string == self.keyword


class NoSnakemakeBlock(ColonBlock):
    """A block starting with `def` or `class`, and only has a single body PythonBlock
    Also contain heading decorators (`@` lines)

    Also, snakemake keywords should not be used in `async` blocks

    TODO: although not recommended, snakemake keywords can be used in
      function/class body
    Should handle that cases in the future
    """

    def consume_body(self, tokens):
        lines, tail_noncoding = tokens.next_block()
        codes = PythonBlock(self.deindent_level + 1, tokens, lines)
        codes.extend_tail_noncoding(tail_noncoding)
        self.body_blocks.append(codes)

    def compilation(self):
        raise NotImplementedError


function_class_blocks: dict[str, type[NoSnakemakeBlock]] = {
    i.lower(): type(i.capitalize(), (NoSnakemakeBlock,), {}) for i in ("def", "class")
}


class IfForTryWithBlock(ColonBlock):
    def consume_body(self, tokens):
        from snakefmt.parser.global_block import GlobalBlock

        blocks = GlobalBlock(self.deindent_level + 1, tokens, []).body_blocks
        self.body_blocks.extend(blocks)

    def compilation(self):
        raise NotImplementedError


class UnknownIndentBlock(IfForTryWithBlock):
    """Although I cannot imadge why an INDENT occurs
    without the control of existing colon keywords, but just in case,
    I will treat the contents as a global block
    """


if_for_try_with_blocks: dict[str, type[IfForTryWithBlock]] = {
    i.lower(): type(i.capitalize(), (IfForTryWithBlock,), {})
    for i in ("if elif else " "for while " "try except finally " "with").split()
}


class CaseBlock(IfForTryWithBlock): ...


class MatchBlock(ColonBlock):
    subautomata = {"case": CaseBlock}

    def consume_body(self, tokens):
        blocks = self.consume_subblocks(tokens, ender_subblock=True)
        if any(not isinstance(i, CaseBlock) for i in blocks):
            raise UnsupportedSyntax(
                f"Unexpected content in {self.keyword} block: "
                f"only `Case` keyword is allowed, but got {blocks}"
            )
        self.body_blocks = blocks

    def compilation(self):
        raise NotImplementedError


class AsyncBlock(NoSnakemakeBlock): ...


python_subautomata: dict[str, type[ColonBlock]] = {
    **function_class_blocks,
    **if_for_try_with_blocks,
    "match": MatchBlock,
    "async": AsyncBlock,
}


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


class SnakemakeBlock(ColonBlock):
    subautomata = {}
    deprecated = {}
    nameable = False
    """an optional identifier may precede the colon (`storage a:`, `input with:`)"""

    @property
    def start_token(self):
        token = super().start_token
        assert token is not None, "SnakemakeBlock should have a start_token"
        return token

    def components(self) -> Iterator[DocumentSymbol]:
        yield from []

    def validate_head(self, allow_suffix=False):
        """A keyword head is `<keyword> [<name>]:`, then a newline."""
        body = self.colon_line.body
        keyword = body[0].string
        for icolon, token in enumerate(body[1:], 1):
            if is_op(":", token):
                break
        else:
            ColonError(line_nb(body[-1]), body[-1].string, keyword)
        if icolon > 1:
            name = body[1]
            if self.nameable:
                if name.type != tokenize.NAME:
                    NotAnIdentifierError(line_nb(name), name.string, keyword)
                if icolon > 2:
                    name = body[2]
                else:
                    name = None
            if name is not None:
                if name.string == "with":
                    # a `with` suffix, accepted only where `nameable` marks it so
                    raise InvalidParameterSyntax(
                        f"'{keyword} with:' is not allowed in this context."
                    )
                else:
                    ColonError(line_nb(name), name.string, keyword)
        if not allow_suffix:
            for i in range(icolon + 1, len(body)):
                token = body[i]
                if effective(token):
                    NewlineError(line_nb(token), body[0].string)

    def consume(self, tokens):
        """Consume tokens until the end of the block head line (the line with `:`)"""
        self.validate_head()
        super().consume(tokens)

    def head_source_line(self) -> str:
        """Original source line of the head, for `# fmt: skip` detection."""
        return self.colon_line.body[0].line

    def raw_source_linestrs(self):
        """Source lines of the block, excluding leading (head_noncoding) comments."""
        yield self.head_source_line()
        for block in self.body_blocks:
            yield from block.full_linestrs

    def compilation(self):
        raise NotImplementedError


class Argument:
    """A single parameter.

    `tokens` are the parameter's expression tokens, ending with a top-level
    comma when the source had one. `tail` holds the comment(s) and newline that
    trail it (e.g. `"a",  # comment`), so `tokens` stays a clean expression.
    """

    def __init__(self, tokens: list[TokenInfo], tail: list[TokenInfo] | None = None):
        self.tokens = tokens
        self.tail = tail if tail is not None else []
        self.is_keyword = self._is_keyword()

    def _is_keyword(self) -> bool:
        body = self.tokens
        if not body:
            return False
        first = body[0]
        for token in body[1:]:
            if token.string.strip() and not token.string.startswith("#"):
                if is_op("=", token):
                    if first.type != tokenize.NAME:
                        raise InvalidParameterSyntax(
                            tokenize.untokenize(self.tokens).strip()
                        )
                    return True
                break
        if is_op("**", first):
            return True
        if is_op("=", first):
            raise InvalidParameterSyntax(tokenize.untokenize(self.tokens).strip())
        return False

    @property
    def has_comma(self) -> bool:
        return bool(self.tokens) and is_op(",", self.tokens[-1])

    @classmethod
    def from_token(cls, tokens: Iterable[TokenInfo]):
        """Split parameter tokens into `Argument`s.

        Parameters are delimited by top-level commas. Each region is handed to
        `_munch` (whole first, then maximal munch by lines). Comment-only lines
        belong to the previous argument, or to `head_noncoding` if none.
        """
        tokeniter = TokenIterator("", iter(tokens))
        process = True
        while process:
            metaarg: list[list[TokenInfo]] = []
            try:
                while True:
                    component = tokeniter.next_component()
                    metaarg.append(component)
                    if len(component) == 1 and is_op(",", component[0]):
                        break
            except UnsupportedSyntax:
                process = False
            if metaarg:
                yield from cls._munch(metaarg)

    @classmethod
    def _munch(cls, region: list[list[TokenInfo]]):
        """Split one comma-delimited region into `Argument`s.

        The whole region is tried first, so implicit string concatenation and
        operator continuations stay a single parameter. Only if the whole region
        is not one valid argument is it split by lines, taking the longest valid
        prefix each time (maximal munch).
        """
        current: list[TokenInfo] = []
        lines = [current]
        for component in region:
            if len(component) == 1:
                (token,) = component
                if not effective(token):
                    if token.type in (tokenize.NL, tokenize.NEWLINE):
                        if current:
                            current += component
                            current = []
                            lines.append(current)
                    # skip
                    continue
            current += component
        while lines:
            n = len(lines)
            while n:
                cand = [t for i in range(n) for t in lines[i]]
                if validate_parameters(cand):
                    if cand:
                        yield cls(cand)
                    lines = lines[n:]
                    break
                n -= 1
            else:
                raise InvalidParameterSyntax(
                    tokenize.untokenize([t for line in lines for t in line]).strip()
                )


class PythonArgumentsBlock(PythonBlock):
    """Manage a directive's indent block and the parent's post-colon content,
    turning both into individual `Argument` parameters.
    """

    def __init__(
        self,
        deindent_level,
        tokens,
        lines=None,
        post_colon: list[TokenInfo] | None = None,
    ):
        super().__init__(deindent_level, tokens, lines)
        self.post_colon = list(post_colon or [])
        self.params = list(Argument.from_token(self.iter))

    @property
    def iter(self):
        """All parameter tokens: post-colon content and the indent body."""
        yield from self.post_colon
        for line in self.head_lines:
            yield from line.iter


class SnakemakeArgumentsBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `input:`, `output:`, etc.
    The content is one PythonArgument or multiple PythonArgument seperated by comma,
    """

    Argument = PythonArgumentsBlock

    @property
    def argument(self):
        assert len(self.body_blocks) == 1
        (block,) = self.body_blocks
        assert isinstance(block, self.Argument)
        return block

    def consume(self, tokens):
        """Split the parameter content into one `Argument` per parameter.

        The tokens after the colon (both inline and indented) are taken out of
        the head line and split into parameters, so each token appears exactly
        once. The original head line is kept as text for `fmt: off` verbatim
        output.
        """
        self.validate_head(allow_suffix=True)
        self.consume_body(tokens)

    def consume_body(self, tokens):
        colon = next(
            i for i, token in enumerate(self.colon_line.body) if is_op(":", token)
        )
        post_colon = self.colon_line.body[colon + 1 :]
        # comments right after the colon belong to the head line, not a parameter
        while post_colon and post_colon[0].type == tokenize.COMMENT:
            post_colon.pop(0)
        peeked: list[TokenInfo] = []
        for token in tokens:
            peeked.append(token)
            if token.type != tokenize.NL and token.type != tokenize.COMMENT:
                break
        tokens.denext(*reversed(peeked))
        if peeked[-1].type != tokenize.INDENT:
            lines, tail = [], []
        else:
            lines, tail = tokens.next_block()
        block = self.Argument(self.deindent_level + 1, tokens, lines, post_colon)
        block.extend_tail_noncoding(tail)
        self.body_blocks = [block]

    trailing_comma = True
    """whether the formatted list ends with a comma"""

    def compilation(self):
        raise NotImplementedError


class SnakemakeUnnamedArgumentsBlock(SnakemakeArgumentsBlock):

    def consume_body(self, tokens):
        super().consume_body(tokens)
        self.check_parameters()

    def check_parameters(self):
        if any(param.is_keyword for param in self.argument.params):
            token = self.start_token
            raise InvalidParameterSyntax(
                f"{line_nb(token)}{token.string} definition "
                f"does not accept key/value parameters"
            )


class SnakemakeUnnamedArgumentBlock(SnakemakeUnnamedArgumentsBlock):
    """Only one unnamed parameter; nothing splits it, so a string may be
    continued over several lines (`shell: "a"\n"b"`). No trailing comma.
    """

    trailing_comma = False

    def check_parameters(self):
        if not self.argument.params:
            token = self.start_token
            raise NoParametersError(f"{line_nb(token)}In {token.string} definition.")
        if len(self.argument.params) > 1:
            token = self.start_token
            raise TooManyParameters(
                f"{line_nb(token)}{token.string} definition expects a single parameter"
            )
        if self.argument.params[0].is_keyword:
            token = self.start_token
            raise InvalidParameter(
                f"{line_nb(token)}{token.string} definition requires a "
                f"positional (not key/value) parameter"
            )


class SnakemakeInlineArgumentBlock(SnakemakeUnnamedArgumentBlock):
    """Inform formatter to try to merge the inline argument into the head line.
    If the line is too long after merging, then keep them separate.
    """


class SnakemakeExecutableBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `run:`, `onstart:`, etc.
    The content is pure python, and must start from the next line after the colon.
    """

    def consume_body(self, tokens):
        lines, tail_noncoding = tokens.next_block()
        executable = PythonBlock(self.deindent_level + 1, tokens, lines)
        executable.extend_tail_noncoding(tail_noncoding)
        self.body_blocks.append(executable)
