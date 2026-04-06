import sys
import tokenize
from abc import ABC, abstractmethod
from typing import Callable, Iterator, Literal, NamedTuple, Optional, Mapping
from tokenize import TokenInfo
from collections import OrderedDict
import black.parsing

from snakefmt.config import read_black_config, Mode


from snakefmt.exceptions import UnsupportedSyntax
from snakefmt.types import TAB

if sys.version_info < (3, 12):
    is_fstring_start = lambda token: False
else:
    is_fstring_start = lambda token: token.type == tokenize.FSTRING_START

    def consume_fstring(tokens: Iterator[TokenInfo]):
        finished: list[TokenInfo] = []
        isin_fstring = 1
        for token in tokens:
            finished.append(token)
            if token.type == tokenize.FSTRING_START:
                isin_fstring += 1
            elif token.type == tokenize.FSTRING_END:
                isin_fstring -= 1
            if isin_fstring == 0:
                break
        return finished


def extract_line_indent(line: str) -> str:
    return line[: len(line) - len(line.lstrip())]


class TokenIterator:
    def __init__(self, name, tokens: Iterator[TokenInfo]):
        self.name = name
        self._live_tokens = tokens
        self._buffered_tokens: list[TokenInfo] = list()
        self.tokens = tokens
        self.lines = 0
        self.rulecount = 0
        self._overwrite_cmd: Optional[str] = None
        self._last_token: Optional[TokenInfo] = None

    def __iter__(self):
        return self

    def next_new_line(self):
        return LogicalLine.from_token(self)

    def next_component(self):
        """Returns the next component, should not break string/bracket pairs"""
        contents: list[TokenInfo] = []
        expect_brackets: list = []
        paired_brackets = {"(": ")", "[": "]", "{": "}"}
        while expect_brackets or not contents:
            token = next(self)
            contents.append(token)
            if token.type == tokenize.OP:
                if token.string in paired_brackets:
                    expect_brackets.append(paired_brackets[token.string])
                elif token.string in ")]}":
                    if not expect_brackets or expect_brackets[-1] != token.string:
                        raise UnsupportedSyntax(
                            f"Unexpected closing bracket {token.string!r} at line {token.start[0]}"
                        )
                    expect_brackets.pop()
            elif is_fstring_start(token):
                contents.extend(consume_fstring(self))
        return contents

    def next_block(self):
        """Returns a entire block, just consume until the end of the block.
        Donot care if there are nested blocks inside or snakemake keywords inside.

        it could be INDEDT -> [any content] -> DEDENT, or [any content] -> DEDENT
        """
        line = self.next_new_line()
        assert line.deindelta >= 0, "Unexpected DEDENT at the beginning of a block"
        assert line.body, "Unexpected empty line at the beginning of a block"
        lines = [line]
        deindelta = 1
        while True:
            # read entire line, dedent if needed
            line = self.next_new_line()
            deindelta += line.deindelta
            if deindelta <= 0:
                deindelta -= line.deindelta
                break
            elif line.end.type == tokenize.ENDMARKER:
                assert deindelta == 1
                break
            lines.append(line)
        # there must be somewhere a DEDENT token to end the block, otherwise raise from __next__
        # now check comments
        indent = extract_line_indent(lines[0].body[0].line)
        tail_noncoding = self.denext_by_indent(line, indent, deindelta)
        return lines, tail_noncoding

    def denext_by_indent(self, line: LogicalLine, indent: str, deindelta=1):
        """Call when a block is ended by a DEDENT token,
        to split comments belong to this block from those belong to parent blocks,
        and reorder tokens so that the next block can be parsed correctly.

        Parameters:
        - line: the line after the block, with DEDENT out of the block
        - indent: the indent string of the ending block,
                  used to determine the belongness of comments
        - deindelta: the number of DEDENT tokens to pop,
                     should be >1 if the block ends at deeper indent levels

        Return: the head_noncoding tokens belongs to the ending block
                according to indents:
            - if block_indent <= extract_line_indent(comments.line):
                - this COMMENT belongs to this block
            - else: afterwards, all COMMENT belongs to parent (or grand-parents) block
                - all NL before this COMMENT belongs to this block

        Dedent the tail_noncoding tokens of a block, and return the dedented tokens.
        The indent level of the tail_noncoding tokens should be the same (or deeper)
         as the block_indent.
        """
        head, dedents, body, end = line
        self.denext(end, *reversed(body), *reversed(dedents[deindelta:]))
        if body and indent:
            assert not body[0].line.startswith(indent), (
                f"indent of ending block(`{indent!r}`) should longer "
                f"than the next line(`{body[0].line!r}`)"
            )
        if not head:
            return dedents[:deindelta]
        for i, token in enumerate(head):
            if token.type == tokenize.COMMENT:
                if not extract_line_indent(token.line).startswith(indent):
                    break
            else:
                assert token.type == tokenize.NL, f"Unexpected token {token!r}"
        else:
            i += 1  # == len(head), push all head tokens back
        self.denext(*reversed(head[i:]))
        return head[:i] + dedents[:deindelta]

    def __next__(self) -> TokenInfo:
        if self._buffered_tokens:
            token = self._buffered_tokens.pop()
        else:
            try:
                token = next(self._live_tokens)
            except StopIteration as e:
                if self._last_token is None:
                    raise UnsupportedSyntax(
                        f"Unexpected content of '{self.name}'"
                    ) from e
                else:
                    raise UnsupportedSyntax(
                        f"Unexpected end of file after symbol[{self._last_token}] while parsing '{self.name}'"
                    ) from e
        self._last_token = token
        return token

    def denext(self, *tokens: TokenInfo) -> None:
        """.denext(a, b, c): next(token) will return c, then b, then a.
        pull back tokens so they can be pushed in the correct order when .next()

        .denext(token, previous_token, ...)
        == .denext(token); .denext(previous_token); ; .denext(...)
        => list(zip(self, range(3))) == [(..., 0), (previous_token, 1), (token, 2)]
        """
        self._buffered_tokens.extend(tokens)


class LogicalLine(NamedTuple):
    head_noncoding: list[TokenInfo]
    deindents: list[TokenInfo]
    body: list[TokenInfo]
    end: TokenInfo

    @property
    def end_op(self):
        body_size = len(self.body)
        if body_size < 2:  # single op line make no sense
            return None
        last_token = self.body[-1]
        if last_token.type == tokenize.COMMENT:
            last_token = self.body[-2]
        if last_token.type != tokenize.OP:
            return None
        return last_token.string

    @property
    def deindelta(self):
        if not self.deindents:
            return 0
        if [i.type for i in self.deindents] == [tokenize.INDENT]:
            return 1
        assert {i.type for i in self.deindents} == {tokenize.DEDENT}
        return -len(self.deindents)

    @property
    def linestrs(self):
        if not self.head_noncoding and self.body:
            if self.body[0].start[0] == self.end.end[0]:
                return [self.body[0].line]
        return tokens2linestrs(iter(self.iter))

    @property
    def iter(self):
        yield from self.head_noncoding
        yield from self.deindents
        yield from self.body
        yield self.end

    @classmethod
    def from_token(cls, tokens: Iterator[TokenInfo]):
        """Returns contents of a entire logical lines (including continued lines),
        also include deindent tokens before it.

        the tokens yield like:

        [NL/COMMENT_LINE] -> [indeents] -> (real content tokens) -> NEWLINE -> (repeat)
        or
        [NL/COMMENT_LINE] -> [DEDENT] -> () -> ENDMARKER
        """

        head_empty_lines: list[TokenInfo] = []
        deindents: list[TokenInfo] = []
        contents: list[TokenInfo] = []
        for token in tokens:
            if token.type == tokenize.NEWLINE or token.type == tokenize.ENDMARKER:
                break
            elif not (contents or deindents) and (
                token.type == tokenize.NL or token.type == tokenize.COMMENT
            ):
                head_empty_lines.append(token)
            elif token.type == tokenize.INDENT or token.type == tokenize.DEDENT:
                assert not contents, "Never expect deindents after any content"
                deindents.append(token)
            else:
                contents.append(token)
        return cls(head_empty_lines, deindents, contents, token)


def split_token_lines(token: TokenInfo):
    """Token can be multiline.
    e.g., `f'''\\nplaintext\\n'''` has these tokens:

        TokenInfo(type=61 (FSTRING_START), string="f'''",
                  start=(21, 0), end=(21, 4), line="f'''\\n")
        TokenInfo(type=62 (FSTRING_MIDDLE), string='\\ncccccccc\\n',
                  start=(21, 4), end=(23, 0), line="f'''\\ncccccccc\\n'''\\n")
        TokenInfo(type=63 (FSTRING_END), string="'''",
                  start=(23, 0), end=(23, 3), line="'''\\n")

    lines should be split to drop overlapping lines and keep unique ones.
    """
    return zip(
        range(token.start[0], token.end[0] + 1), token.line.splitlines(keepends=True)
    )


def tokens2linestrs(tokens: Iterator[TokenInfo]):
    """Convert a sequence of tokens into a list of strings, one for each line.
    ignore deindents (may be reorganized from next few lines)
    """

    lines: dict[int, str] = {}
    # Lines that are interior to a multiline token (string / f-string body).
    # Their content must not be reindented.
    string_interior_lines: set[int] = set()
    for token in tokens:
        if not_deindent(token) and token.end[0] not in lines:
            lines.update(split_token_lines(token))
            if token.start[0] != token.end[0]:
                string_interior_lines.update(
                    range(token.start[0] + 1, token.end[0] + 1)
                )
    newlines: list[str] = []
    for i in sorted(lines):
        line = lines[i]
        if i in string_interior_lines:
            assert newlines, "block cannot start inner a multiline-string"
            newlines[-1] += line
        else:
            newlines.append(line)
    return newlines


def not_deindent(token: TokenInfo) -> bool:
    return token.type != tokenize.INDENT and token.type != tokenize.DEDENT


class FormatState(NamedTuple):
    fmt_off: bool = False
    sort_direcives: bool = False

    def update(self, *str):
        # TODO: implement state update logic
        return self._replace()


class Block(ABC):
    """
    A block can be:
        a continuous python code of lines with the same indentation level.
            Also include functions, classes and decoraters (`@` lines)
        a single block identifed by keywords in `{PYTHON_INDENT_KEYWORDS}`
            and all the code under it, until the next block of the same or lower indent level.
        a snakemake keyword block (rule, module, config, etc.)
            and all the code under it, until the next block of the same or lower indent level.
            snakemake keywords should NEVER in functions or classes
        comments between blocks
            (exclude the comment right before the indenting keyword, which is considered part of the block)

    Starting of blocks (file or new indent):
        the space and comments until the first indenting keyword are considered a block of their own.
    All other spaces are considered part of the previous block's trailing empty lines.

    Comment belongness:
        Only comments with neither empty lines between/after the next block nor different indent levels
            are considered part of the same block.
        e.g.:
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

    Indent of comments:
        determined by the following real code line and previous indents.

        Durning parsing tokens, when a comment token is encountered,
        its effective indent level is not directly knowable.

        principles:
            follow_indent = indent of the following real code line
            if EOF:
                follow_indent = 0
            rule 1 (always):
                indent of comments >= follow_indent
            rule 2 (if follow_indent < self.indents[-1]):
                indent of comments = epsilon + max(
                    i for i in self.indents if i <= comment_indent
                )
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
        return []

    @abstractmethod
    def consume(self, tokens: TokenIterator) -> None: ...

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

        Used in GlobalBlock and SnakemakeKeywordBlock, to consume their body blocks.
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
        return [i for line in self.head_lines for i in line.linestrs]

    @property
    def full_linestrs(self) -> list[str]:
        """return the code splited by lines, but should keep multiline-string or multiline-f-string complete,
        to make trimming and reformatting easier.

        Should and Only should be rewrite for pure python blocks.
        """
        lines = (
            self.head_linestrs
            + [line for block in self.body_blocks for line in block.full_linestrs]
            + tokens2linestrs(iter(self.tail_noncoding))
        )
        return lines

    def components(self) -> "Iterator[DocumentSymbol]":
        """
        - position := (file, line number, column number)
        - type := name / rule, input, output / function, class / etc.
            if not a name, then that's the definition of the name (should link blank names to here)
        - identifier := the identifier of the block, e.g. rule `a`, `input`, input `b`, etc.
            when iterating sub-blocks in rule, identifier should modified to reflect the parent block, e.g. `rules.a.input.b`
            (`b` may be difficult to identify, but at least we know the content of `input` block)
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
    def formatted(self, mode: Mode, state: FormatState) -> tuple[str, FormatState]:
        """return formatted code of the block"""

    @abstractmethod
    def compilation(self):
        """return pure python code compiled from the block, without snakemake keywords and comments"""


class DocumentSymbol(NamedTuple):
    name: str
    detail: str
    symbol_kind: str
    position_start: tuple[int, int]
    position_end: tuple[int, int]
    block: "Block"


def format_black(raw: str, mode: Mode, indent=0, partial: Literal["", ":", "("] = ""):
    """Format a string using Black formatter.

    if indent:
        prefix = make series of `{' ' * i}if 1:\\n` to increase indent level
        format(prefix + string)
        remove first `indent` lines
    if partial == ":":
        safe_indent = longest(prefix spacing)
        format(string + f"\\n{safe_indent} pass")
        remove the last line
    if partial == "(":
        format("f(" + string + ")")
        if string.startswith("f(\\n"):
            remove the first line and the last line
        else:
            remove first three characters and the last character
    """
    prefix = ""
    for i in range(indent):
        prefix += " " * i + "if 1:\n"
    if partial == ":":
        # for block such as if/else/...
        safe_indent = max(extract_line_indent(line) for line in prefix.splitlines())
        string = raw + f"\n{safe_indent} pass"
    elif partial == "(":
        string = "f(\n" + raw + "\n)"
    else:
        string = raw
    try:
        fmted = black.format_str(prefix + string, mode=mode)
    except black.parsing.InvalidInput as e:
        raise e
    if indent:
        fix = fmted.split("\n", indent)[-1]
    else:
        fix = fmted
    if partial == ":":
        fix = fix.rstrip().rsplit("\n", 1)[0] + "\n"
    elif partial == "(":
        if string.startswith("f(\n"):
            fix = fix.split("\n", 1)[1].rsplit("\n", 1)[0] + "\n"
        else:
            fix = fix[2:-1]
    return fix


class PythonBlock(Block):
    """Hold `head_lines` and `tail_noncoding`, no `body_blocks`"""

    def consume(self, tokens):
        "Do nothing, win"

    def formatted(self, mode, state):
        raw = "".join(self.full_linestrs)
        formatted = format_black(raw, mode, self.deindent_level)
        return formatted, state

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

    @property
    def prior_colon(self): ...

    @property
    def post_colon(self): ...

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
    def consume_body(self, tokens: TokenIterator) -> None: ...

    def recognises(self, token: TokenInfo):
        return token.type == tokenize.NAME and token.string == self.keyword


class NoSnakemakeBlock(ColonBlock):
    """A block starting with `def` or `class`, and only has a single body PythonBlock
    Also contain heading decorators (`@` lines)

    Also, snakemake keywords should not be used in `async` blocks

    TODO: although not recommended, snakemake keywords can be used in function/class body
    Should handle that cases in the future
    """

    def consume_body(self, tokens):
        lines, tail_noncoding = tokens.next_block()
        self.body_blocks.append(PythonBlock(self.deindent_level + 1, tokens, lines))
        self.extend_tail_noncoding(tail_noncoding)

    def formatted(self, mode, state):
        raw = "".join(self.full_linestrs)
        formatted = format_black(raw, mode, self.deindent_level)
        return formatted, state

    def compilation(self):
        raise NotImplementedError


function_class_blocks: dict[str, type[NoSnakemakeBlock]] = {
    i.lower(): type(i.capitalize(), (NoSnakemakeBlock,), {}) for i in ("def", "class")
}


class IfForTryWithBlock(ColonBlock):
    def consume_body(self, tokens):
        blocks = GlobalBlock(self.deindent_level + 1, tokens, []).body_blocks
        self.body_blocks.extend(blocks)

    def formatted(self, mode, state):
        formatted = []
        if self.body_blocks:
            raw = "".join(self.full_linestrs)
            return format_black(raw, mode, self.deindent_level), state
        raw_head = "".join(self.head_linestrs)
        head = format_black(raw_head, mode, self.deindent_level, partial=":")
        formatted.append(head)
        state_ = state
        if isinstance(
            self.body_blocks[0],
            (NoSnakemakeBlock, NamedBlock, SnakemakeExecutableBlock),
        ):
            formatted.append("\n")
        for block in self.body_blocks:
            block_formatted, state_ = block.formatted(mode, state_)
            formatted.append(block_formatted)
            formatted.append("\n")
        formatted.pop()  # remove the last "\n"
        for comment in tokens2linestrs(iter(self.tail_noncoding)):
            formatted.append(TAB * self.deindent_level + comment.lstrip())
        return "".join(formatted), state_

    def compilation(self):
        raise NotImplementedError


class UnknownIndentBlock(IfForTryWithBlock):
    """Although I cannot imadge why an INDENT occurs
    without the control of existing colon keywords, but just in case,
    I will treat the contents as a global block
    """


PYTHON_INDENT_KEYWORDS = {
    i
    for j in ("if elif else", "for while", "try except finally", "with")
    for i in j.split()
}

if_for_try_with_blocks: dict[str, type[IfForTryWithBlock]] = {
    i.lower(): type(i.capitalize(), (IfForTryWithBlock,), {})
    for i in PYTHON_INDENT_KEYWORDS
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

    def formatted(self, mode, state):
        raise NotImplementedError

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

    def components(self) -> Iterator[DocumentSymbol]:
        yield from []

    def formatted(self, mode, state):
        raise NotImplementedError

    def compilation(self):
        raise NotImplementedError


class PythonArgumentsBlock(PythonBlock):
    """Block inside snakemake directives,
    such as `data.txt` in `input: \n    "data.txt"`

    Only allow:
    - simple expressions on the right, e.g. `"data.txt",`
    - assignment with simple names on the left, e.g. `a = 1,`
    - Specally, allow `*args` and `**kwargs` as normal function

    Enhancement could be done: accepth expressions without trailing comma,
    because each expression is already splitted by lines,
    and we can add a trailing comma only if needed.
    If we want to support expressions without trailing comma,
    cases where two lines can makesense without a comma between them
      should be carefully considered,
    e.g.:
        input:
            "data.txt"
            "data2.txt"
        params:
            sth
            (a, b)
    Although in our view this is naturally two expressions,
    the action do change with the proposed enhancement.
    """


class PythonOneLineArgument(PythonArgumentsBlock):
    """Only allow simple expressions on the right"""


class PythonListArguments(PythonArgumentsBlock):
    """Only allow simple expressions on the right, and the whole block should be a list"""


class PythonListDictArguments(PythonArgumentsBlock):
    """Parsed as *args, **kwargs"""


class SnakemakeOneLineArgumentsBlock(SnakemakeBlock):
    def consume_body(self, tokens):
        lines, tail_noncoding = tokens.next_block()
        self.body_blocks.append(
            PythonOneLineArgument(self.deindent_level + 1, tokens, lines)
        )
        self.extend_tail_noncoding(tail_noncoding)

    def formatted(self, mode, state):
        raise NotImplementedError

    def compilation(self):
        raise NotImplementedError


def init_block_register():
    def register_block(name: Optional[str] = None):
        def decorator(type_: type[SnakemakeBlock]):
            keyword = name or type_._keyword()
            namespace[keyword] = type_
            return type_

        return decorator

    namespace: OrderedDict[str, type[SnakemakeBlock]] = OrderedDict()
    return namespace, register_block


global_snakemake_subautomata, _register = init_block_register()


@_register()
class Include(SnakemakeOneLineArgumentsBlock): ...


@_register()
class Workdir(SnakemakeOneLineArgumentsBlock): ...


@_register()
class Configfile(SnakemakeOneLineArgumentsBlock): ...


@_register("pepfile")
class Set_Pepfile(SnakemakeOneLineArgumentsBlock): ...


@_register()
class Pepschema(SnakemakeOneLineArgumentsBlock): ...


@_register()
class Report(SnakemakeOneLineArgumentsBlock): ...


@_register()
class Ruleorder(SnakemakeOneLineArgumentsBlock): ...


@_register("singularity")
@_register("container")
class Global_Container(SnakemakeOneLineArgumentsBlock): ...


@_register("containerized")
class Global_Containerized(SnakemakeOneLineArgumentsBlock): ...


@_register("conda")
class Global_Conda(SnakemakeOneLineArgumentsBlock): ...


class SnakemakeListArgumentsBlock(SnakemakeBlock):
    def consume_body(self, tokens):
        lines, tail_noncoding = tokens.next_block()
        self.body_blocks.append(
            PythonListArguments(self.deindent_level + 1, tokens, lines)
        )
        self.extend_tail_noncoding(tail_noncoding)

    def formatted(self, mode, state):
        raise NotImplementedError

    def compilation(self):
        raise NotImplementedError


@_register("envvars")
class Register_Envvars(SnakemakeListArgumentsBlock): ...


@_register()
class Localrules(SnakemakeListArgumentsBlock): ...


@_register()
class InputFlags(SnakemakeListArgumentsBlock): ...


@_register()
class OutputFlags(SnakemakeListArgumentsBlock): ...


class SnakemakeListDictArgumentsBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `input:`, `output:`, etc.
    The content is pure python.
    """

    def consume_body(self, tokens):
        lines, tail_noncoding = tokens.next_block()
        self.body_blocks.append(
            PythonListDictArguments(self.deindent_level + 1, tokens, lines)
        )
        self.extend_tail_noncoding(tail_noncoding)

    def formatted(self, mode, state):
        raise NotImplementedError

    def compilation(self):
        raise NotImplementedError


@_register("wildcard_constraints")
class Global_Wildcard_Constraints(SnakemakeListDictArgumentsBlock): ...


@_register()
class Scattergather(SnakemakeListDictArgumentsBlock): ...


@_register("resource_scope")
class ResourceScope(SnakemakeListDictArgumentsBlock): ...


@_register("storage")
class Storage(SnakemakeListDictArgumentsBlock): ...


@_register("pathvars")
class Register_Pathvars(SnakemakeListDictArgumentsBlock): ...


class SnakemakeExecutableBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `run:`, `onstart:`, etc.
    The content is pure python.
    """

    def consume_body(self, tokens):
        lines, tail_noncoding = tokens.next_block()
        self.body_blocks.append(PythonBlock(self.deindent_level + 1, tokens, lines))
        self.extend_tail_noncoding(tail_noncoding)


@_register()
class OnStart(SnakemakeExecutableBlock): ...


@_register()
class OnSuccess(SnakemakeExecutableBlock): ...


@_register()
class OnError(SnakemakeExecutableBlock): ...


class SnakemakeKeywordBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `rule:`, `module:`, etc.
    The contents are other snakemake blocks.
    """

    def consume_body(self, tokens):
        blocks = self.consume_subblocks(tokens, ender_subblock=True)
        if any(not isinstance(i, SnakemakeBlock) for i in blocks):
            raise UnsupportedSyntax(
                f"Unexpected content in {self.keyword} block: "
                f"only snakemake blocks are allowed, but got {blocks}"
            )
        self.body_blocks = blocks


@_register()
class Module(NamedBlock, SnakemakeKeywordBlock):
    subautomata, _register = init_block_register()

    @_register()
    class Name(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Snakefile(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Meta_Wrapper(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Skip_Validation(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Config(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Pathvars(SnakemakeListDictArgumentsBlock): ...

    @_register()
    class Prefix(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Replace_Prefix(SnakemakeOneLineArgumentsBlock): ...


@_register("use")
class UseRule(NamedBlock, SnakemakeKeywordBlock):
    subautomata, _register = init_block_register()

    @_register()
    class Name(SnakemakeOneLineArgumentsBlock): ...

    @_register("default_target")
    class Default_Target_Rule(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Input(SnakemakeListDictArgumentsBlock): ...

    @_register()
    class Output(SnakemakeListDictArgumentsBlock): ...

    @_register()
    class Log(SnakemakeListDictArgumentsBlock): ...

    @_register()
    class Benchmark(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class RulePathvars(SnakemakeListDictArgumentsBlock): ...

    @_register("wildcard_constraints")
    class Register_Wildcard_Constraints(SnakemakeListDictArgumentsBlock): ...

    @_register("cache")
    class Cache_Rule(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Priority(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Retries(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Group(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class LocalRule(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Handover(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Shadow(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Conda(SnakemakeOneLineArgumentsBlock): ...

    @_register("singularity")
    @_register()
    class Container(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Containerized(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class EnvModules(SnakemakeListArgumentsBlock): ...

    @_register()
    class Threads(SnakemakeOneLineArgumentsBlock): ...

    @_register()
    class Resources(SnakemakeListDictArgumentsBlock): ...

    @_register()
    class Params(SnakemakeListDictArgumentsBlock): ...

    @_register()
    class Message(SnakemakeOneLineArgumentsBlock): ...

    deprecated = {"version": "Use conda or container directive instead (see docs)."}


@_register()
class Rule(UseRule):
    exec_subautomata, _register = init_block_register()

    @_register()
    class Run(SnakemakeExecutableBlock): ...

    class AbstractCmd(SnakemakeOneLineArgumentsBlock, Run): ...

    @_register()
    class Shell(AbstractCmd): ...

    @_register()
    class Script(AbstractCmd): ...

    @_register()
    class Notebook(Script): ...

    @_register()
    class Wrapper(Script): ...

    @_register("template_engine")
    class TemplateEngine(Script): ...

    @_register()
    class CWL(Script): ...

    subautomata = {**UseRule.subautomata, **exec_subautomata}


@_register()
class Checkpoint(Rule): ...


class GlobalBlock(Block):
    """Hold `body_blocks` only, no `head_lines` nor `tail_noncoding`

    all blocks in `body_blocks` should in the
      same deindent level as GlobalBlock itself
    so tail_noncoding always updated to the last body_block
    """

    subautomata = {**python_subautomata, **global_snakemake_subautomata}

    def consume(self, tokens):
        self.body_blocks = self.consume_subblocks(tokens)

    def formatted(self, mode, state):
        formatted = []
        state_ = state
        linesep = "\n" if self.deindent_level else "\n\n"
        for block in self.body_blocks:
            block_formatted, state_ = block.formatted(mode, state_)
            formatted.append(block_formatted)
            formatted.append(linesep)
        if formatted:
            formatted.pop()  # remove the last "\n"
        return "".join(formatted), state_

    def compilation(self):
        raise NotImplementedError


def parse(input: str | Callable[[], str], name: str = "<string>") -> GlobalBlock:
    if isinstance(input, str):
        tokens = tokenize.generate_tokens(
            iter(input.splitlines(keepends=True)).__next__
        )
    else:
        tokens = tokenize.generate_tokens(input)
    return GlobalBlock(0, TokenIterator(name, tokens), [])
