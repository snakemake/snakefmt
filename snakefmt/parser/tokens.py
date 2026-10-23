"""Token-level utilities: iterating tokens, grouping them into logical lines.

:class:`TokenIterator` consumes Python's ``tokenize`` stream,
adds the ability to look at one whole logical line at a time,
push tokens back when a lookahead turns out not to belong to the current construct.

:class:`LogicalLine` splits a line into four parts:
- comment/blank prefix,
- indentation deltas,
- body tokens
- terminating ``NEWLINE``/``ENDMARKER``.
"""

import ast
import io
import sys
import tokenize
from tokenize import TokenInfo
from typing import Iterator, NamedTuple, Optional

from snakefmt.exceptions import EndOfInput, InvalidPython, UnsupportedSyntax


def line_nb(token: TokenInfo) -> str:
    """for error messages."""
    return f"L{token.start[0]}: "


def is_op(op: str, token: TokenInfo):
    return token.type == tokenize.OP and token.string == op


def not_deindent(token: TokenInfo):
    return token.type not in (tokenize.INDENT, tokenize.DEDENT)


def effective(token: TokenInfo):
    """Whether ``token`` carries content"""
    return token.type != tokenize.COMMENT and token.string.strip()


if sys.version_info < (3, 12):

    def is_fstring_start(token: TokenInfo):
        """Before Python 3.12 f-strings are a single STRING token."""
        return False

else:

    def is_fstring_start(token: TokenInfo):
        """Whether ``token`` opens an f-string (Python 3.12+ tokenization)."""
        return token.type == tokenize.FSTRING_START

    def consume_fstring(tokens: Iterator[TokenInfo]):
        """Consume tokens up to and including the end of the current f-string.

        Nested f-strings are tracked,
        so the returned list contains the whole f-string token group.
        """
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
    """Return the leading whitespace"""
    return line[: len(line) - len(line.lstrip())]


def splitlines(text: str):
    """Split ``text`` at ``\\n`` only, keeping the line endings.

    ``str.splitlines`` treats a number of characters (form feed, vertical tab,
    ``\\x1c``-``\\x1e``, ``\\x85``, ``\\u2028``, ``\\u2029``) as line boundaries
    while :mod:`tokenize` does not.  Splitting on them would silently drop the
    rest of such a line, so mirror tokenize's behaviour here.
    """
    return io.StringIO(text)


class TokenIterator:
    """A ``tokenize.TokenInfo`` iterator that can buffer and push back tokens."""

    def __init__(self, name, tokens: Iterator[TokenInfo]):
        """``name`` is used in error messages to describe what is being parsed."""

        self.name = name
        self._live_tokens = tokens
        self._buffered_tokens: list[TokenInfo] = list()
        self.lines = 0
        self.rulecount = 0
        self._overwrite_cmd: Optional[str] = None
        self._last_token: Optional[TokenInfo] = None

    def next_new_line(self):
        return LogicalLine.from_token(self)

    def next_component(self):
        """Returns the next component, should not break string/bracket pairs.

        A `lambda ... :` parameter list is also one component,
        so its top-level commas / `=` are never mistaken for parameter separators.
        """

        contents: list[TokenInfo] = []
        # expected closers on one stack: `)`/`]`/`}` for brackets, `:` for a lambda
        expect_brackets: list[str] = []
        paired_brackets = {"(": ")", "[": "]", "{": "}"}
        while expect_brackets or not contents:
            token = next(self)
            contents.append(token)
            if token.type == tokenize.OP:
                if token.string in paired_brackets:
                    expect_brackets.append(paired_brackets[token.string])
                elif token.string in (")", "]", "}"):
                    if not expect_brackets or expect_brackets[-1] != token.string:
                        raise UnsupportedSyntax(
                            f"{line_nb(token)}Unexpected closing bracket "
                            f"{token.string!r}"
                        )
                    expect_brackets.pop()
                elif expect_brackets and token.string == ":" == expect_brackets[-1]:
                    expect_brackets.pop()
            elif token.type == tokenize.NAME and token.string == "lambda":
                expect_brackets.append(":")
            elif is_fstring_start(token):
                contents.extend(consume_fstring(self))
        return contents

    def next_block(self) -> "tuple[list[LogicalLine], list[TokenInfo]]":
        """
        Returns a list of logical lines and a list of tail_noncoding
        of the same (or inner) deindent level as the first line of the block.

        Do not care if there are nested blocks inside or snakemake keywords inside.

        it could be INDENT -> [any content] -> DEDENT, or [any content] -> DEDENT
        """

        line = self.next_new_line()
        if line.end.type == tokenize.ENDMARKER:
            self.denext(*reversed(list(line.iter)))
            return [], []
        token = line.body[0] if line.body else line.end
        if line.deindelta < 0:
            raise IndentationError(
                f"{line_nb(token)}Unexpected DEDENT at the beginning of a block"
            )
        if not line.body:
            raise IndentationError(
                f"{line_nb(token)}Unexpected empty line at the beginning of a block"
            )
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
        # there must be somewhere a DEDENT token to end the block,
        # otherwise raise from __next__ now check comments
        indent = extract_line_indent(lines[0].body[0].line)
        tail_noncoding = self.denext_by_indent(line, indent, deindelta)
        return lines, tail_noncoding

    def denext_by_indent(self, line: "LogicalLine", indent: str, deindelta=1):
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

    def __iter__(self):
        return self

    def __next__(self) -> TokenInfo:
        """Turns an unexpected end of the token stream into an
        :class:`UnsupportedSyntax` error mentioning what was being parsed.
        """
        if self._buffered_tokens:
            token = self._buffered_tokens.pop()
        else:
            try:
                token = next(self._live_tokens)
            except StopIteration as e:
                if self._last_token is None:
                    raise EndOfInput(f"Unexpected content of '{self.name}'") from e
                else:
                    raise EndOfInput(
                        f"Unexpected end of file after symbol"
                        f"[{self._last_token}] while parsing '{self.name}'"
                    ) from e
            except tokenize.TokenError as e:
                # report exact line
                message, (line, column) = e.args
                if message != "EOF in multi-line string" and self._last_token is not None:
                    line = self._last_token.start[0]
                raise InvalidPython(
                    f"Tokenization error:\n```\n"
                    f"Cannot parse: {line}:{column}: {message}\n```\n"
                ) from None
        self._last_token = token
        return token

    @property
    def rest(self):
        """Yield all remaining tokens without ``UnsupportedSyntax``"""
        while self._buffered_tokens:
            yield self._buffered_tokens.pop()
        yield from self._live_tokens

    def denext(self, *tokens: TokenInfo) -> None:
        """.denext(a, b, c): next(token) will return c, then b, then a.
        pull back tokens so they can be pushed in the correct order when .next()

        .denext(token, previous_token, ...)
        == .denext(token); .denext(previous_token); ; .denext(...)
        => list(zip(self, range(3))) == [(..., 0), (previous_token, 1), (token, 2)]
        """
        self._buffered_tokens.extend(tokens)


class LogicalLine(NamedTuple):
    """One logical line of Python source, split into token groups.

    It is a single line of source code,
    possibly continued across multiple physical lines.
    A complete python expression cannot be split
     by new line inside multiline strings or brackets,
    logical line handles that correctly.
    """

    head_noncoding: list[TokenInfo]
    """blank lines and comments before the line"""
    deindents: list[TokenInfo]
    """leading ``INDENT``/``DEDENT`` tokens"""
    body: list[TokenInfo]
    """the content tokens"""
    end: TokenInfo
    """NEWLINE or ENDMARKER"""

    @property
    def endswith_colon(self):
        """Will expect a block body after this line,
        and this head line does not contain any content after the colon.
        """
        body_size = len(self.body)
        if body_size < 2:  # single op line make no sense
            return None
        last_token = self.body[-1]
        if last_token.type == tokenize.COMMENT:
            last_token = self.body[-2]
        return is_op(":", last_token)

    @property
    def deindelta(self):
        """Net indentation change before this line"""
        if not self.deindents:
            return 0
        if [i.type for i in self.deindents] == [tokenize.INDENT]:
            return 1
        assert {i.type for i in self.deindents} == {tokenize.DEDENT}
        return -len(self.deindents)

    @property
    def linestrs(self):
        """The source lines belonging to it."""
        if not self.head_noncoding and self.body:
            if self.body[0].start[0] == self.end.end[0]:
                return [self.body[0].line]
        return tokens2linestrs(iter(self.iter))

    @property
    def iter(self):
        """Yield all tokens of the line in source order."""
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
            # split multiline tokens with lineno for dereplication
            lines.update(
                zip(range(token.start[0], token.end[0] + 1), splitlines(token.line))
            )
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


def validate_parameters(tokens: list[TokenInfo]):
    """Whether `tokens` parse as a single call argument."""
    text = tokenize.untokenize(tokens).strip()
    try:
        ast.parse(f"param({text}\n)")
    except SyntaxError:
        return False
    return True
