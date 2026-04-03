import sys
import tokenize
from abc import ABC, abstractmethod
from typing import Callable, Iterable, Iterator, NamedTuple, Optional
from tokenize import TokenInfo


from snakefmt.exceptions import UnsupportedSyntax

if sys.version_info < (3, 12):
    is_fstring_start = lambda token: False
else:
    is_fstring_start = lambda token: token.type == tokenize.FSTRING_START

    def consume_fstring(tokens: TokenIterator):
        finished: list[TokenInfo] = []
        isin_fstring = 1
        while True:
            token = next(tokens)
            finished.append(token)
            if token.type == tokenize.FSTRING_START:
                isin_fstring += 1
            elif token.type == tokenize.FSTRING_END:
                isin_fstring -= 1
            if isin_fstring == 0:
                break
        return finished


def extract_indent(token: TokenInfo) -> str:
    line = token.line
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
        """Returns contents of a entire logical lines (including continued lines),
        also include indent tokens before it.

        the tokens yield like:

        [NL/COMMENT_LINE] -> [INDENT] -> (real content tokens) -> NEWLINE -> (repeat)
        """
        head_empty_lines: list[TokenInfo] = []
        indents: list[TokenInfo] = []
        contents: list[TokenInfo] = []
        while True:
            token = next(self)
            if token.type == tokenize.NEWLINE or token.type == tokenize.ENDMARKER:
                return head_empty_lines, indents, contents, token
            elif not (contents or indents) and (
                token.type == tokenize.NL or token.type == tokenize.COMMENT
            ):
                head_empty_lines.append(token)
            elif token.type == tokenize.INDENT or token.type == tokenize.DEDENT:
                assert not contents, "Never expect indent after any content"
                indents.append(token)
            else:
                contents.append(token)

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
        block_contents: list[TokenInfo] = []
        head_empty_lines, indents, contents, token = self.next_new_line()
        assert not indents or (
            [i.type for i in indents] == [tokenize.INDENT]
        ), f"Unexpected indents {indents!r}"
        assert contents, "Unexpected empty line"
        block_contents.extend(head_empty_lines + indents + contents + [token])
        indent_level = 1
        while True:
            # read entire line, dedent if needed
            head_empty_lines, indents, contents, token = self.next_new_line()
            if indents:
                if [i.type for i in indents] == [tokenize.INDENT]:
                    indent_level += 1
                else:
                    assert {i.type for i in indents} == {
                        tokenize.DEDENT
                    }, f"Unexpected indents {indents!r}"
                    indent_level -= len(indents)
                    if indent_level <= 0:
                        # now it is used to represent `DEDENTs to keep`
                        # e.g. indent_level=1, 2 DEDENTs -> went 1 too deep -> keep 1
                        indent_level += len(indents)
                        self.denext(
                            token,
                            *reversed(contents),
                            *reversed(indents[indent_level:]),
                        )
                        break
            if token.type == tokenize.ENDMARKER and indent_level == 1:
                self.denext(token, *reversed(contents))
                break
            block_contents.extend(head_empty_lines + indents + contents + [token])
        # there must be somewhere a DEDENT token to end the block, otherwise raise from __next__
        # now check comments
        indent = extract_indent(block_contents[0])
        block_contents.extend(self.dedent_tail_noncoding(head_empty_lines, indent))
        block_contents.extend(indents[:indent_level])
        return block_contents

    def dedent_tail_noncoding(self, tokens: list[TokenInfo], block_indent: str):
        """Call at the end of a block,
        split comments belong to this block from those belong to parent blocks,
        and reorder .
        Dedent the tail_noncoding tokens of a block, and return the dedented tokens.
        The indent level of the tail_noncoding tokens should be the same as the block_indent.

        Should control tail_noncoding of the block:
        - all NL belongs to this block
        - if block_indent <= extract_indent(comments):
            - this COMMENT belongs to this block
        - else: afterwards, all COMMENT belongs to parent (or grand-parents) block
        """
        if not tokens:
            return []
        for i, token in enumerate(tokens):
            if token.type == tokenize.COMMENT:
                if not extract_indent(token).startswith(block_indent):
                    break
            else:
                assert token.type == tokenize.NL, f"Unexpected token {token!r}"
        self.denext(*reversed(tokens[i:]))
        return tokens[:i]

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


PYTHON_INDENT_KEYWORDS = {
    i
    for j in ("if elif else", "for while", "try except finally", "with")
    for i in j.split()
}


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


def block_lines(tokens: Iterator[TokenInfo]):
    lines: dict[int, str] = {}
    # Lines that are interior to a multiline token (string / f-string body).
    # Their content must not be reindented.
    string_interior_lines: set[int] = set()
    for token in tokens:
        if not_indent(token) and token.end[0] not in lines:
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


def not_indent(token: TokenInfo) -> bool:
    return token.type != tokenize.INDENT and token.type != tokenize.DEDENT


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

    __slots__ = (
        "indent_level",
        "head_noncoding",
        "head_tokens",
        "sub_blocks",
        "tail_noncoding",
    )

    def __init__(
        self, tokens: TokenIterator, indent_level: int, head_tokens: list[TokenInfo]
    ) -> None:
        self.sub_blocks: list["Block"] = []
        self.head_noncoding: list[TokenInfo] = []
        self.tail_noncoding: list[TokenInfo] = []
        self.head_tokens = head_tokens
        self.indent_level = indent_level
        self.consume(tokens)

    def extend_tail_noncoding(self, tokens: list[TokenInfo]):
        self.tail_noncoding.extend(tokens)
        return []

    def extend_head_noncoding(self, tokens: list[TokenInfo]):
        """Test if the tokens are all non-coding, and if so, extend head_noncoding with them and return True.
        Otherwise, return False and do not modify head_noncoding.
        """
        assert not self.head_noncoding, "head_noncoding should be empty before extend"
        if {i.type for i in tokens} <= {tokenize.NL, tokenize.COMMENT}:
            self.head_noncoding = tokens
            return True
        return False

    @abstractmethod
    def consume(self, tokens: TokenIterator) -> None: ...

    @property
    def start_token(self):
        if not self.head_tokens:
            raise UnsupportedSyntax("Unexpected empty block")
        return self.head_tokens[0]

    @property
    def raw_indent(self) -> str:
        "tell the raw indent of the block"
        assert self.start_token is not None, "start_token should be set after consume()"
        return self.start_token.line[: self.start_token.start[1]]

    def block_lines(self):
        return block_lines(iter(self.head_tokens))

    def raw(self):
        """return the code splited by lines, but should keep multiline-string or multiline-f-string complete,
        to make trimming and reformatting easier.

        Should and Only should be rewrite for pure python blocks.
        """
        lines = (
            block_lines(filter(not_indent, self.head_noncoding))
            + self.block_lines()
            + [line for block in self.sub_blocks for line in block.raw()]
            + block_lines(filter(not_indent, self.tail_noncoding))
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
        for block in self.sub_blocks:
            yield from block.components()

    @abstractmethod
    def formatted(self) -> str:
        """return formatted code of the block"""

    @abstractmethod
    def compilation(self) -> str:
        """return pure python code compiled from the block, without snakemake keywords and comments"""


class DocumentSymbol(NamedTuple):
    name: str
    detail: str
    symbol_kind: str
    position_start: tuple[int, int]
    position_end: tuple[int, int]
    block: "Block"


class PythonBlock(Block):
    """Hold `head_tokens` only, no tokens comments, no sub-blocks"""

    def consume(self, tokens):
        "Do nothing, win"

    def formatted(self):
        raise NotImplementedError

    def compilation(self):
        raise NotImplementedError

    def components(self):
        yield from []


class ColonBlock(Block):
    @classmethod
    def _keyword(cls):
        return cls.__name__.lower()

    @property
    def keyword(self) -> str:
        return self._keyword()

    __slots__ = ("post_colon_coding",)

    def __init__(self, tokens, indent_level, head_tokens):
        self.post_colon_coding: list[TokenInfo] = []
        super().__init__(tokens, indent_level, head_tokens)

    def consume(self, tokens):
        """Consume tokens until the end of the block head line (the line with `:`)"""
        token = next(tokens)
        if token.type != tokenize.INDENT:
            tokens.denext(token)
            token_iter = TokenIterator("", iter(self.head_tokens))
            colon_index = 0
            while True:
                token, *rest = token_iter.next_component()
                if not rest and token.type == tokenize.OP and token.string == ":":
                    break
                colon_index += 1 + len(rest)
            self.post_colon_coding = self.head_tokens[colon_index + 1 :]
        else:
            self.consume_body(tokens)

    @abstractmethod
    def consume_body(self, tokens: TokenIterator) -> None: ...

    def recognises(self, token: TokenInfo):
        return token.type == tokenize.NAME and token.string == self.keyword


class FunctionClassBlock(ColonBlock):
    def consume_body(self, tokens):
        contents = tokens.next_block()
        self.sub_blocks.append(PythonBlock(tokens, self.indent_level + 1, contents))

    def formatted(self):
        raise NotImplementedError

    def compilation(self):
        raise NotImplementedError


function_class_blocks: dict[str, type[FunctionClassBlock]] = {
    i.lower(): type(i.capitalize(), (FunctionClassBlock,), {}) for i in ("def", "class")
}


class IfForTryWithBlock(ColonBlock):
    def consume_body(self, tokens):
        """Consume tokens until the end of the block head line (the line with `:`)"""
        global_block = GlobalBlock(tokens, self.indent_level + 1, [])
        self.sub_blocks.append(global_block)

    def formatted(self):
        raise NotImplementedError

    def compilation(self):
        raise NotImplementedError


if_for_try_with_blocks: dict[str, type[IfForTryWithBlock]] = {
    i.lower(): type(i.capitalize(), (IfForTryWithBlock,), {})
    for i in PYTHON_INDENT_KEYWORDS
}


class SnakemakeBlock(ColonBlock):
    __slots__ = ("name",)
    name: str

    subautomata: dict[str, Block] = {}
    deprecated: dict[str, str] = {}

    def components(self):
        this_symbol = DocumentSymbol(
            name=self.name,
            detail="\n".join(i.rstrip() for i in self.block_lines()).strip("\n"),
            symbol_kind=self._keyword(),
            position_start=self.start_token.start,
            position_end=self.head_tokens[-1].end,
            block=self,
        )
        yield this_symbol


global_snakemake_blocks: dict[str, type[SnakemakeBlock]] = {}


class CommentBlock(Block): ...


class GlobalBlock(Block):
    subautomata = (
        function_class_blocks | if_for_try_with_blocks | global_snakemake_blocks
    )

    def consume(self, tokens):
        """pass through all tokens until the next indenting keyword,
        and check if there is any non-comment content.
        """
        plain_python_tokens: list[TokenInfo] = []
        end_token: Optional[TokenInfo] = None
        block_depth = 0
        indent_str = "[TBD]"
        while not end_token or end_token.type != tokenize.ENDMARKER:
            head_empty_lines, indents_, contents_, end_token = tokens.next_new_line()
            if indents_:
                if indents_[0].type == tokenize.INDENT:
                    assert len(indents_) == 1, f"Unexpected INDENTs {indents_!r}"
                    # there should be only one INDENT token at the beginning of the block
                    if block_depth == 0 and indent_str == "[TBD]":
                        indent_str = extract_indent(indents_[0])
                    else:
                        block_depth += 1
                else:
                    assert {t.type for t in indents_} == {
                        tokenize.DEDENT
                    }, f"Unexpected DEDENTs {indents_!r}"
                    if block_depth:
                        block_depth -= 1
                    else:
                        # get out of the block
                        tokens.denext(
                            end_token,
                            *reversed(contents_),
                            *reversed(indents_[1:]),
                        )
                        head_empty_ = iter(head_empty_lines)
                        for token in head_empty_:
                            if token.type == tokenize.COMMENT:
                                if extract_indent(token).startswith(indent_str):
                                    self.tail_noncoding.append(token)
                                else:
                                    break
                            else:
                                self.tail_noncoding.append(token)
                        head_empty_lines1 = list(head_empty_)
                        tokens.denext(*reversed(list(head_empty_)))
                        head_empty_lines = head_empty_lines1
                        break
            had_plain_python = len(plain_python_tokens)
            if head_empty_lines:
                if self.sub_blocks and not plain_python_tokens:
                    plain_python_tokens = self.sub_blocks[-1].extend_tail_noncoding(
                        head_empty_lines
                    )
                else:
                    plain_python_tokens.extend(head_empty_lines)
            if contents_:
                token = contents_[0]
                if token.type == tokenize.NAME and token.string in self.subautomata:
                    indent_level = self.indent_level + block_depth + 1
                    colon_block = self.subautomata[token.string](
                        tokens, indent_level, [*contents_, end_token]
                    )
                    if colon_block.extend_head_noncoding(head_empty_lines):
                        plain_python_tokens = plain_python_tokens[:had_plain_python]
                    if plain_python_tokens:
                        self.sub_blocks.append(
                            PythonBlock(tokens, self.indent_level, plain_python_tokens)
                        )
                    self.sub_blocks.append(colon_block)
                    plain_python_tokens = []
                else:
                    plain_python_tokens.extend((*contents_, end_token))
            else:
                plain_python_tokens.append(end_token)
        if plain_python_tokens:
            self.sub_blocks.append(
                PythonBlock(tokens, self.indent_level, plain_python_tokens)
            )

    def formatted(self):
        raise NotImplementedError

    def compilation(self):
        raise NotImplementedError


def parse(input: str | Callable[[], str], name: str = "<string>") -> GlobalBlock:
    if isinstance(input, str):
        tokens = tokenize.generate_tokens(
            iter(input.splitlines(keepends=True)).__next__
        )
    else:
        tokens = tokenize.generate_tokens(input)
    return GlobalBlock(TokenIterator(name, tokens), 0, [])


def token_indents_updated(token: TokenInfo, indents: list[str]) -> bool:
    if token.type == tokenize.INDENT:
        line = token.line
        indent = line[: len(line) - len(line.lstrip())]
        if indent not in indents:
            indents.append(indent)
    elif token.type == tokenize.DEDENT:
        line = token.line
        indent = line[: len(line) - len(line.lstrip())]
        while indents and indents[-1] != indent:
            indents.pop()
    else:
        return False
    return True
