import ast
import io
import re
import sys
import tokenize
from abc import ABC, abstractmethod
from collections import OrderedDict
from tokenize import TokenInfo
from typing import (
    Callable,
    Generator,
    Iterable,
    Iterator,
    Literal,
    Mapping,
    NamedTuple,
    Optional,
    TypeVar,
)

import black.parsing

from snakefmt.config import Mode, read_black_config
from snakefmt.exceptions import (
    ColonError,
    EmptyContextError,
    InvalidParameter,
    InvalidParameterSyntax,
    InvalidPython,
    NewlineError,
    NoParametersError,
    NotAnIdentifierError,
    SyntaxFormError,
    TooManyParameters,
    UnsupportedSyntax,
)
from snakefmt.shell_formatter import format_python_string_literal

TAB = "    "  # PEP8, indentation will be coded as 4 spaces
_FMT_DIRECTIVE_RE = re.compile(
    r"^# fmt: (off|on)(?:\[(\w+(?:,\s*\w+)*)\])?(?=$|\s{2}|\s#)"
)


def _line_nb(token: TokenInfo) -> str:
    return f"L{token.start[0]}: "


def _is_op(op: str, token: TokenInfo):
    return token.type == tokenize.OP and token.string == op


def _validate_parameters(tokens: list[TokenInfo]):
    """Whether `tokens` parse as a single call argument."""
    text = tokenize.untokenize(tokens).strip()
    try:
        ast.parse(f"param({text}\n)")
    except SyntaxError:
        return False
    return True


if sys.version_info < (3, 12):

    def is_fstring_start(token: TokenInfo):
        return False

else:

    def is_fstring_start(token: TokenInfo):
        return token.type == tokenize.FSTRING_START

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
        self.lines = 0
        self.rulecount = 0
        self._overwrite_cmd: Optional[str] = None
        self._last_token: Optional[TokenInfo] = None

    def __iter__(self):
        return self

    def next_new_line(self):
        return LogicalLine.from_token(self)

    def next_component(self):
        """Returns the next component, should not break string/bracket pairs.

        A `lambda ... :` parameter list is also one component, so its top-level
        commas / `=` are never mistaken for parameter separators.
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
                            f"Unexpected closing bracket "
                            f"{token.string!r} at line {token.start[0]}"
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
        """Returns a entire block, just consume until the end of the block.
        Do not care if there are nested blocks inside or snakemake keywords inside.

        it could be INDENT -> [any content] -> DEDENT, or [any content] -> DEDENT
        """

        line = self.next_new_line()
        if line.end.type == tokenize.ENDMARKER:
            self.denext(*reversed(list(line.iter)))
            return [], []
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
                        f"Unexpected end of file after symbol"
                        f"[{self._last_token}] while parsing '{self.name}'"
                    ) from e
        self._last_token = token
        return token

    @property
    def rest(self):
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
    head_noncoding: list[TokenInfo]
    deindents: list[TokenInfo]
    body: list[TokenInfo]
    end: TokenInfo
    """NEWLINE or ENDMARKER"""

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


def not_deindent(token: TokenInfo) -> bool:
    return token.type != tokenize.INDENT and token.type != tokenize.DEDENT


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
                zip(
                    range(token.start[0], token.end[0] + 1),
                    token.line.splitlines(keepends=True),
                )
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


class FormatState(NamedTuple):
    fmt_on: bool = True
    sort_directives: bool | None = None
    skip_next: bool = False  # one-time directive for the next snakemake block
    format_shell: bool = False
    # custom directive order overriding the default `subautomata` order;
    # empty means "use the default order". Directives missing from the custom
    # list keep their default (subautomata) position, which puts actions last.
    rule_order: tuple[str, ...] = ()
    module_order: tuple[str, ...] = ()

    @property
    def not_format(self):
        return not self.fmt_on or self.skip_next

    def update(self, comment: str):
        """check single line comment line for pattern:
        ```
        # fmt: off
        # fmt: off[option1, option2, ...]
        # fmt: on
        # fmt: on[option1, option2, ...]
        ```

        Currently, options can be:
        - sort: whether to sort snakemake directives (e.g. input, output, params, etc.)
        - next: whether to apply the directive to the next snakemake block only
            Do not effect blocks after empty lines.
            Cannot be disabled by `# fmt: on[next]`
        - only the first directive will be applied

        If found `# fmt: on` and no `# fmt: off` before:
            if `fmt: off[sort]` is False:
                    sort_directives == True  -> enabled
                    sort_directives == False -> disabled in this indent before
                    sort_directives == None  -> haven't enabled originally
                turn it on
        """
        if match := _FMT_DIRECTIVE_RE.match(comment):
            directive, options = match.groups()
            # Parse options: "sort,next" -> ["sort", "next"] -> "sort"
            option = [opt.strip() for opt in (options or "").split(",")][0]
            if not self.fmt_on:  # only check `# fmt: on`
                if directive == "on" and not option:
                    return self._replace(fmt_on=True)
            elif directive == "on":
                if option == "sort":
                    return self._replace(sort_directives=True)
                if self.sort_directives is False:
                    # re-enable sorting if it was disabled by `# fmt: off[sort]` before,
                    # but should effect if no `# fmt: off[sort]` in this indent before.
                    return self._replace(sort_directives=True)
            elif directive == "off":
                if option == "sort":
                    return self._replace(sort_directives=False)
                if option == "next":
                    return self._replace(skip_next=True)
                return self._replace(fmt_on=False)
        return self

    def consume_skip_next(self) -> "FormatState":
        """Returns new state with skip_next consumed (set to False)"""
        if self.skip_next:
            return self._replace(skip_next=False)
        return self

    @staticmethod
    def found_skip(comment: str):
        return "# fmt: skip" in comment

    def reset_sort(self):
        if self.sort_directives is False:
            return self._replace(sort_directives=None)
        return self


def format_black(
    raw: str,
    mode: Mode,
    indent=0,
    partial: Literal["", ":", "("] = "",
    start_token: TokenInfo | None = None,
) -> str:
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
        prefix += " " * i + "def a():\n"
    if partial == ":":
        # for block such as if/else/...
        safe_indent = max(extract_line_indent(line) for line in raw.splitlines())
        string = raw + f"{safe_indent} pass"
    elif partial == "(":
        # Tb() effects equals to a entire new indent
        string = " " * indent + "Tb(\n" + raw + "\n)"
    else:
        string = raw
    try:
        fmted = black.format_str(prefix + string, mode=mode)
    except black.parsing.InvalidInput as e:
        if start_token is not None:
            match = re.search(r"(Cannot parse.*?:\s*)(?P<line>\d+)(.*)", str(e))
            if match:
                err_msg = match.group(1) + str(start_token.start[0]) + match.group(3)
            else:
                err_msg = str(e)
        else:
            err_msg = str(e)
        err_msg += (
            "\n\n(Note reported line number may be incorrect, as"
            " snakefmt could not determine the true line number)"
        )
        err_msg = f"Black error:\n```\n{str(err_msg)}\n```\n"
        raise InvalidPython(err_msg) from None
    if indent:
        fix = fmted.split("\n", indent)[-1]
    else:
        fix = fmted
    if partial == ":":
        fix = fix.rstrip().rsplit("\n", 1)[0] + "\n"
    elif partial == "(":
        fix = fix.strip()
        if fix.startswith("Tb(\n"):
            fix = fix.split("\n", 1)[1].rsplit("\n", 1)[0] + "\n"
        else:
            if "#" not in fix:  # safe to unpack function
                fix = TAB * (indent + 1) + fix[3:-1] + "\n"
            else:
                fix = (
                    format_black(raw + "\n#", mode, indent, partial).rsplit("\n", 2)[0]
                    + "\n"
                )
    return fix


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

    def segment2format(
        self, mode: Mode, state: FormatState
    ) -> Generator[tuple[str, str | None], None, None]:
        """yield:
        - [unformated_python_code, None]
        - [formated_snakemake_code, indent_str]

        `SnakemakeInlineArgumentBlock` should be taken very careful of,
        since they are formatedd as `def` blocks, and may not sperate from
        blocks with different keywords. So here are the special principles
        specially for one-line snakemake blocks:

        - the previous block should be in the same indent of current block;
        - if previous line (with no newline nor comments) is:
                1, `def` block; or
                2. another one-line block with differnt keyword:
            then add a newline
        - if previous line is the same keyword with:
                only comment lines but NO blank line between:
            merge the two lines into one block, with comments in between
        - (doesn't matter if this block is actually one-line or not)
        """
        # comment fmt directives in head_linestrs
        #  will effect on post blocks of the same indent,
        # so should be updated during the parent body_blocks iteration.
        for line in self.head_linestrs:
            yield line, None
        last_keyword = ""
        line = ""
        state = state.reset_sort()
        for block in self.body_blocks:
            restart_state = state = state.consume_skip_next()
            # update state from head_noncoding
            for head_line in block.head_lines:
                for noncoding_token in head_line.head_noncoding:
                    if noncoding_token.type == tokenize.COMMENT:
                        state = state.update(noncoding_token.string)
                    elif state.skip_next and not noncoding_token.line.strip():
                        state = state.consume_skip_next()
            if isinstance(block, ColonBlock):
                if block.keyword == "def":
                    if last_keyword and last_keyword != "def":
                        # Oh, differnt keyword detected, so (last)line must exists
                        # Then check if that line is start
                        if (
                            line.rstrip()
                            .rsplit("\n", 1)[-1]
                            .startswith(block.indent_str + last_keyword)
                        ):
                            # If NO any line before the first line of this block,
                            # black cannot split them: Add one to force splitting
                            if not block.head_lines[0].head_noncoding:
                                yield "\n", None
                    last_keyword = "def"
                    for line, indent in block.segment2format(mode, state):
                        # record `line` for next useage
                        yield line, indent
                elif isinstance(block, SnakemakeBlock):
                    for line, indent in block.segment2format(
                        mode, restart_state, last_keyword
                    ):
                        yield line, indent
                    last_keyword = block.keyword
                else:
                    last_keyword = ""
                    yield from block.segment2format(mode, state)
            else:
                last_keyword = ""
                yield from block.segment2format(mode, state)
        if self.tail_noncoding:
            yield "".join(tokens2linestrs(iter(self.tail_noncoding))), None

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

    def formatted(self, mode: Mode):
        raw = "".join(self.full_linestrs)
        if not raw.strip():
            return ""
        formatted = format_black(
            raw, mode, self.deindent_level, start_token=self.head_lines[0].body[0]
        )
        return formatted

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
            if len(component) == 1 and _is_op(":", *component):
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


def deindent_lines(old_indent: str, target_indent_level: int, lines: Iterable[str]):
    target_indent = TAB * target_indent_level
    return [
        target_indent + line[len(old_indent) :] if line.startswith(old_indent) else line
        for line in lines
    ]


def _effective(token: TokenInfo):
    return token.type != tokenize.COMMENT and token.string.strip()


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
            if _is_op(":", token):
                break
        else:
            ColonError(_line_nb(body[-1]), body[-1].string, keyword)
        if icolon > 1:
            name = body[1]
            if self.nameable:
                if name.type != tokenize.NAME:
                    NotAnIdentifierError(_line_nb(name), name.string, keyword)
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
                    ColonError(_line_nb(name), name.string, keyword)
        if not allow_suffix:
            for i in range(icolon + 1, len(body)):
                token = body[i]
                if _effective(token):
                    NewlineError(_line_nb(token), body[0].string)

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

    def segment2format(self, mode: Mode, state: FormatState, last_keyword=""):
        """yield:
        - [unformated_python_code, None]
        - [formated_snakemake_code, indent]

        If state.skip_next is True, or state.fmt_on is False,
        return unformatted content with proper True/False markers.
        """

        # Get noncoding_lines early to check fmt directives
        indent_str = TAB * self.deindent_level
        assert len(self.head_lines) == 1, "Snakemake keywords should only in one line"
        noncoding_lines: list[str] = []
        last_fmt_on = state.fmt_on
        # Check if there's fmt: on/off in noncoding_lines to update state
        for noncoding_line in tokens2linestrs(iter(self.colon_line.head_noncoding)):
            if not noncoding_line.strip():
                last_keyword = ""
            else:
                state = state.update(noncoding_line.lstrip())
            if state.not_format:
                noncoding_lines.append(noncoding_line)
            else:
                noncoding_lines.append(
                    indent_str + format_black(noncoding_line, mode, 0)
                )
        if last_fmt_on and state.fmt_on:
            if last_keyword == self.keyword:
                # pre-format these lines and yield together
                pre_formatted = format_black(
                    "".join(noncoding_lines), mode, 0
                ).splitlines(keepends=True)
                for line in pre_formatted:
                    if state.found_skip(line):
                        yield line, None
                    else:
                        yield indent_str + line.lstrip(), self.indent_str
            else:
                if not noncoding_lines:
                    yield "\n", None
                yield "".join(noncoding_lines), None
        else:
            yield "".join(noncoding_lines), None

        # Check if this block should be skipped from formatting
        if state.not_format:
            raw = "".join(
                deindent_lines(
                    self.indent_str,
                    self.deindent_level,
                    self.raw_source_linestrs(),
                )
            )
            # Trailing blank lines from body_blocks belong to the next block's
            # separator, not this block's content. Strip extra trailing blank
            # lines so the compilation loop doesn't double-count them with
            # black's blank-line insertion.
            if raw.endswith("\n\n") and state.skip_next:
                n_trailing_space = len(raw) - len(raw.rstrip("\n")) - 1
                raw = raw.rstrip("\n") + "\n"
            else:
                n_trailing_space = 0
            yield raw, self.indent_str
            if n_trailing_space > 0:
                yield "\n" * n_trailing_space, None
        else:
            yield self.formatted(mode, state), self.indent_str
        if self.tail_noncoding:
            yield "".join(tokens2linestrs(iter(self.tail_noncoding))), None

    def formatted(self, mode: Mode, state: FormatState):
        formatted_prior, post_colon = self.format_head(mode)
        formatted_body = self.format_body(mode, state, post_colon)
        formatted = [formatted_prior, formatted_body]
        return "".join(formatted)

    def format_head(self, mode: Mode) -> tuple[str, list[TokenInfo]]:
        """Format the head line, up to and including the colon.

        Parameters (inline included) live in `body_blocks`, so no post-colon
        tokens are returned; a trailing comment on the colon line is kept here.
        """
        indent = TAB * self.deindent_level
        source_line = self.head_source_line()
        if FormatState.found_skip(source_line):
            return indent + source_line.lstrip(), []
        prior_colon, post_colon = self.split_colon_line()
        assert len(prior_colon) == 1, "Snakemake keywords should be in one line"
        (head,) = prior_colon
        components = head.strip().split()
        formatted_head = indent + " ".join(components) + ":"
        if self.colon_line.end_op == ":":
            # only a single line comment or empty is possible here, add directly
            colon_token = next(post_colon)
            post = tokens2linestrs(post_colon.rest)
            if post:
                post[0] = post[0][colon_token.end[1] :]
                fake_str = "if 1:" + "".join(post) + "   ..."
                fake_fmt = format_black(fake_str, mode).strip()
                formatted_head += fake_fmt.split(":", 1)[1].rsplit("\n", 1)[0]
        return formatted_head + "\n", []

    @abstractmethod
    def format_body(
        self, mode: Mode, state: FormatState, post_colon: list[TokenInfo]
    ) -> str:
        """Return the formatted body of the block,
        mode: black mode
        state: format state,
        post_colon: tokens after the colon in the head line.
            If any, must start with the colon
        """

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
                if _is_op("=", token):
                    if first.type != tokenize.NAME:
                        raise InvalidParameterSyntax(
                            tokenize.untokenize(self.tokens).strip()
                        )
                    return True
                break
        if _is_op("**", first):
            return True
        if _is_op("=", first):
            raise InvalidParameterSyntax(tokenize.untokenize(self.tokens).strip())
        return False

    @property
    def has_comma(self) -> bool:
        return bool(self.tokens) and _is_op(",", self.tokens[-1])

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
                    if len(component) == 1 and _is_op(",", component[0]):
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
                if not _effective(token):
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
                if _validate_parameters(cand):
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

    def format_post_colon(
        self, mode: Mode, deindent_level: int, trailing_comma=True
    ) -> str:
        """If there is indent after the colon line,
        even if expressions exist in that line,
        indent body should be formatted as part of the cotent:
            input: balabal,  # <- expression after the colon
                balabal2     # <- indent body, should format as part of the content
        to:
            input:
                balabal,
                balabal2,

        Morover, the original snakefmt allow sort positional arguments
          before keyword arguments. Here need check, too

        Input:
            post_colon: tokens after the colon in the head line,
                    e.g. `balabal,` in the above example
                post_colon[0] := TokenInfo(type=NAME, string='balabal', ...)
            body_blocks: indent body blocks,
                    e.g. the block of `balabal2` in the above example
        """
        first = next(self.iter)
        lines: dict[int, str] = {}
        for token in self.iter:
            lines.update(
                zip(
                    range(token.start[0], token.end[0] + 1),
                    token.line.splitlines(keepends=True),
                )
            )
        if not lines:
            return ""

        def source(start: tuple[int, int], end: tuple[int, int]) -> str:
            """The block source text between two (line, col) positions, half-open."""
            if start[0] == end[0]:
                return lines[start[0]][start[1] : end[1]]
            text = lines[start[0]][start[1] :]
            for row in range(start[0] + 1, end[0]):
                text += lines[row]
            text += lines[end[0]][: end[1]]
            return text

        # Collect, in source order, everything between the previous parameter's
        # end and this one's end (so nothing in between is lost).
        start = first.start
        slices: list[tuple[Argument, str]] = []
        for param in self.params:
            if not param.tokens:
                continue
            end = param.tokens[-1].end
            slices.append((param, source(start, end)))
            start = end

        # positional (unnamed) before keyword
        slices.sort(key=lambda param_text: param_text[0].is_keyword)

        parts = []
        for param, text in slices:
            if trailing_comma != param.has_comma:
                if trailing_comma:
                    text += "\n,"
                else:
                    text = text.rstrip(",")
            parts.append(text)
        parts.append(source(start, token.end))
        tail_noncoding = "".join(tokens2linestrs(iter(self.tail_noncoding)))
        formatable = "".join(parts) + tail_noncoding
        return format_black(
            formatable,
            mode,
            deindent_level,
            partial="(",
            start_token=first,
        )


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
            i for i, token in enumerate(self.colon_line.body) if _is_op(":", token)
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

    def format_body(self, mode, state, post_colon) -> str:
        """Format the parameters, positional before keyword, one per line."""
        if state.found_skip(self.head_source_line()):
            return ""
        return self.argument.format_post_colon(
            mode, self.deindent_level, self.trailing_comma
        )

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
                f"{_line_nb(token)}{token.string} definition "
                f"does not accept key/value parameters"
            )


class SnakemakeUnnamedArgumentBlock(SnakemakeUnnamedArgumentsBlock):
    """Only one unnamed parameter; nothing splits it, so a string may be
    continued over several lines (`shell: "a"\\n"b"`). No trailing comma.
    """

    trailing_comma = False

    def check_parameters(self):
        if not self.argument.params:
            token = self.start_token
            raise NoParametersError(f"{_line_nb(token)}In {token.string} definition.")
        if len(self.argument.params) > 1:
            token = self.start_token
            raise TooManyParameters(
                f"{_line_nb(token)}{token.string} definition expects a single parameter"
            )
        if self.argument.params[0].is_keyword:
            token = self.start_token
            raise InvalidParameter(
                f"{_line_nb(token)}{token.string} definition requires a "
                f"positional (not key/value) parameter"
            )


class SnakemakeInlineArgumentBlock(SnakemakeUnnamedArgumentBlock):

    def formatted(self, mode, state):
        """Try to merge the inline argument into the head line.
        If the line is too long after merging, then keep them separate.
        """
        formatted_prior, post_colon = self.format_head(mode)
        formatted_body = self.format_body(mode, state, post_colon)
        formatted = [formatted_prior, formatted_body]
        if formatted_body.count("\n") == 1 and formatted_body.endswith("\n"):
            if formatted_prior.count("\n") > 1:
                prev, last_head_line = formatted_prior[:-1].rsplit("\n", 1)
                prev += "\n"
            else:
                prev, last_head_line = "", formatted_prior[:-1]
            if formatted_prior.endswith(":\n") and "#" not in last_head_line:
                formatted_merge = last_head_line + " " + formatted_body.lstrip()
                if len(formatted_merge) <= mode.line_length:
                    formatted = [prev + formatted_merge]
        return "".join(formatted)


def init_block_register():
    T = TypeVar("T", bound=SnakemakeBlock)

    def register_block(name: Optional[str] = None):
        def decorator(type_: type[T]) -> type[T]:
            keyword = name or type_._keyword()
            namespace[keyword] = type_
            return type_

        return decorator

    namespace: OrderedDict[str, type[SnakemakeBlock]] = OrderedDict()
    return namespace, register_block


global_snakemake_subautomata, _register = init_block_register()


@_register()
class Include(SnakemakeInlineArgumentBlock): ...


@_register()
class Workdir(SnakemakeInlineArgumentBlock): ...


@_register()
class Configfile(SnakemakeInlineArgumentBlock): ...


@_register("pepfile")
class Set_Pepfile(SnakemakeInlineArgumentBlock): ...


@_register()
class Pepschema(SnakemakeInlineArgumentBlock): ...


@_register()
class Report(SnakemakeInlineArgumentBlock): ...


@_register()
class Ruleorder(SnakemakeInlineArgumentBlock): ...


@_register("singularity")
@_register("container")
class Global_Container(SnakemakeInlineArgumentBlock): ...


@_register("containerized")
class Global_Containerized(SnakemakeInlineArgumentBlock): ...


@_register("conda")
class Global_Conda(SnakemakeInlineArgumentBlock): ...


@_register("envvars")
class Register_Envvars(SnakemakeUnnamedArgumentsBlock): ...


@_register()
class Localrules(SnakemakeUnnamedArgumentsBlock): ...


@_register()
class InputFlags(SnakemakeUnnamedArgumentsBlock): ...


@_register()
class OutputFlags(SnakemakeUnnamedArgumentsBlock): ...


@_register("wildcard_constraints")
class Global_Wildcard_Constraints(SnakemakeArgumentsBlock): ...


@_register()
class Scattergather(SnakemakeArgumentsBlock): ...


@_register("resource_scopes")
class ResourceScope(SnakemakeArgumentsBlock): ...


@_register()
class Storage(SnakemakeArgumentsBlock):
    nameable = True


@_register("pathvars")
class Register_Pathvars(SnakemakeArgumentsBlock): ...


class SnakemakeExecutableBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `run:`, `onstart:`, etc.
    The content is pure python, and must start from the next line after the colon.
    """

    def consume_body(self, tokens):
        lines, tail_noncoding = tokens.next_block()
        executable = PythonBlock(self.deindent_level + 1, tokens, lines)
        executable.extend_tail_noncoding(tail_noncoding)
        self.body_blocks.append(executable)

    def format_body(self, mode, state, post_colon):
        assert not post_colon, "python must start on a new line"
        (param_space,) = self.body_blocks
        assert isinstance(param_space, PythonBlock), "Unexpected body block type"
        return param_space.formatted(mode)


@_register()
class OnStart(SnakemakeExecutableBlock): ...


@_register()
class OnSuccess(SnakemakeExecutableBlock): ...


@_register()
class OnError(SnakemakeExecutableBlock): ...


class SnakemakeDirectiveBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `rule:`, `module:`, etc.
    The contents are other snakemake blocks.
    """

    nameable = True

    def consume_body(self, tokens):
        blocks = self.consume_subblocks(tokens, ender_subblock=True)
        keyword = self.colon_line.body[0].string
        no_content = True
        for block in blocks:
            if isinstance(block, SnakemakeBlock):
                no_content = False
                continue
            if not isinstance(block, PythonBlock):
                rep = block.start_token or self.start_token
                raise UnsupportedSyntax(
                    f"{_line_nb(rep)}Unexpected content in "
                    f"{keyword} block: {rep.line}"
                )
            code = [
                token
                for line in block.head_lines
                for token in line.iter
                if _effective(token)
            ]
            if len(code) == 1 and code[0].type == tokenize.STRING:
                no_content = False
                continue
            if not code:
                continue
            rep = block.start_token
            if rep is not None:
                if rep.type == tokenize.NAME:
                    raise SyntaxError(
                        f"{_line_nb(rep)}Unrecognised keyword "
                        f"{rep.string!r} in {keyword} definition"
                    )
            else:
                rep = self.start_token
            raise SyntaxError(
                f"{_line_nb(rep)}Invalid python code in "
                f"{keyword} definition: {rep.line}"
            )
        if no_content:
            raise EmptyContextError(
                f"{_line_nb(self.colon_line.body[0])}{keyword} has no "
                f"keywords attached to it."
            )
        self.body_blocks = blocks

    @abstractmethod
    def get_order(self, state: FormatState) -> tuple[str, ...]: ...

    def format_body(self, mode, state, post_colon):
        """Sort directives in the order of subautomata,
        and format them together with the head line.
        """
        assert not post_colon, "Invalid inline contents"
        formatted: list[str] = []
        directives: dict[str, str] = {}
        tail_noncoding: list[str] = []
        indent = TAB * (self.deindent_level + 1)
        order = self.get_order(state)
        for block in self.body_blocks:
            assert not tail_noncoding, "no tail_noncoding before body_blocks"
            if isinstance(block, PythonBlock):
                formatted.append(block.formatted(mode))
                for line in block.head_linestrs:
                    state = state.update(line.lstrip())
                # A blank line the user wrote between the docstring
                # and the first directive is kept
                if len(self.body_blocks) > 1:
                    block = self.body_blocks[1]
                    assert isinstance(
                        block, SnakemakeBlock
                    ), "Unexpected block type in snakemake keyword block"
                    following = block.colon_line.head_noncoding
                    if following and following[0].type == tokenize.NL:
                        formatted.append("\n")
                continue
            assert isinstance(
                block, SnakemakeBlock
            ), "Unexpected block type in snakemake keyword block"
            noncoding = tokens2linestrs(iter(block.colon_line.head_noncoding))
            directive = ""
            for line in noncoding:  # here noncoding is already formated
                linelstrip = line.lstrip()
                last_sort_off = state.sort_directives
                if linelstrip:
                    # only non-empty lines are formattable
                    if state.found_skip(linelstrip):
                        directive += line
                    else:
                        directive += indent + format_black(linelstrip, mode, 0)
                    state = state.update(linelstrip)
                if state.not_format:
                    if directives:
                        formatted.extend(self.sort_directives(directives, order))
                    if directive:
                        formatted.append(directive)
                        directive = ""
                    if not linelstrip:
                        formatted.extend(
                            deindent_lines(
                                block.indent_str, self.deindent_level + 1, [line]
                            )
                        )
                elif not state.sort_directives:
                    if directives:
                        formatted.extend(self.sort_directives(directives, order))
                    if directive:
                        formatted.append(directive)
                        directive = ""
                elif not last_sort_off:
                    # state.sort_directives switched on, this comment is
                    #  actually `# fmt: on[sort]` directive,
                    # so split from next directive
                    formatted.append(directive)
                    directive = ""
            if state.not_format:
                formatted.extend(
                    deindent_lines(
                        block.indent_str,
                        self.deindent_level + 1,
                        block.raw_source_linestrs(),
                    )
                )
            else:
                directive += block.formatted(mode, state)
                if state.sort_directives:
                    directives[block.start_token.string] = directive
                else:
                    assert not directives, "Already flushed once fmt: off[sort]"
                    formatted.append(directive)
            if block.tail_noncoding:
                tail_noncoding = tokens2linestrs(iter(block.tail_noncoding))
            # no `\n` between
        if directives:
            formatted.extend(self.sort_directives(directives, order))
        if tail_noncoding:
            tail_noncoding = [i.lstrip().rstrip("\n") for i in tail_noncoding]
            formatted.extend(f"{indent}{i}\n" for i in tail_noncoding if i)
        return "".join(formatted)

    @classmethod
    def sort_directives(cls, directives: dict[str, str], order: tuple[str, ...] = ()):
        """Yield the directives sorted by `order`, then by the subautomata order
        for any directive not listed. Clears `directives`."""
        for keyword in order:
            if keyword in directives:
                yield directives.pop(keyword)
        if directives:
            for keyword in cls.subautomata:
                if keyword in directives:
                    yield directives.pop(keyword)
        assert not directives, f"Unknown directives: {', '.join(directives)}"


@_register()
class Module(NamedBlock, SnakemakeDirectiveBlock):
    subautomata, _register = init_block_register()

    @_register()
    class Name(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Pathvars(SnakemakeArgumentsBlock): ...

    # Reference
    @_register()
    class Snakefile(SnakemakeUnnamedArgumentBlock): ...

    # Override
    @_register()
    class Config(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Skip_Validation(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Prefix(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Replace_Prefix(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Meta_Wrapper(SnakemakeUnnamedArgumentBlock): ...

    def get_order(self, state):
        return state.module_order


class _Rule(NamedBlock, SnakemakeDirectiveBlock):
    subautomata, _register = init_block_register()

    @_register()
    class Name(SnakemakeUnnamedArgumentBlock): ...

    @_register("default_target")
    class Default_Target_Rule(SnakemakeInlineArgumentBlock): ...

    # I/O
    @_register()
    class Input(SnakemakeArgumentsBlock): ...

    @_register()
    class Output(SnakemakeArgumentsBlock): ...

    @_register()
    class Log(SnakemakeArgumentsBlock): ...

    @_register()
    class Benchmark(SnakemakeUnnamedArgumentBlock): ...

    # Rule logic
    @_register()
    class Pathvars(SnakemakeArgumentsBlock): ...

    @_register("wildcard_constraints")
    class Register_Wildcard_Constraints(SnakemakeArgumentsBlock): ...

    # Scheduling & control
    @_register("cache")
    class Cache_Rule(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Priority(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Retries(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Group(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class LocalRule(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Handover(SnakemakeInlineArgumentBlock): ...

    # Execution environment
    @_register()
    class Shadow(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Conda(SnakemakeUnnamedArgumentBlock): ...

    @_register("singularity")
    @_register()
    class Container(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Containerized(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class EnvModules(SnakemakeUnnamedArgumentsBlock): ...

    # Execution resources and parameters

    @_register()
    class Threads(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Resources(SnakemakeArgumentsBlock): ...

    @_register()
    class Params(SnakemakeArgumentsBlock): ...

    # Runtime messages
    @_register()
    class Message(SnakemakeUnnamedArgumentBlock): ...

    deprecated = {"version": "Use conda or container directive instead (see docs)."}

    def get_order(self, state):
        return state.rule_order


@_register("use")
class UseRule(_Rule):

    _EBNF = (
        '"use" "rule" (identifier | "*") '
        '"from" identifier '
        '["exclude" identifier {"," identifier}] '
        '["as" identifier] ["with" ":"]'
    )

    def validate_head(self, allow_suffix=False):
        body = self.colon_line.body
        line = body[0].line.split("#", 1)[0].strip()

        def fail():
            raise SyntaxFormError(_line_nb(body[0]), line, self._EBNF)

        def is_identifier(token: str):
            return re.fullmatch(r"[a-zA-Z_]\w*", token) is not None

        def is_glob(token: str):
            return re.fullmatch(r"[a-zA-Z_][\w*]*", token) is not None

        # commas may be surrounded by spaces; make them separate tokens
        tokens = line.replace(",", " , ").split()
        if tokens[:2] != ["use", "rule"]:
            fail()

        # reading a *required* token past the end is a syntax error, so those
        # reads are left unguarded and `IndexError` -> `fail()`. Optional
        # trailing parts (e.g. `from ...` alone) are guarded with `i < len`.
        try:
            whitelist = [tokens[2]]
            i = 3
            # the whitelist must be followed by a keyword, so running past the
            # end here is a syntax error (IndexError -> fail())
            while tokens[i] == ",":
                whitelist.append(tokens[i + 1])
                i += 2
            if whitelist != ["*"]:
                if "*" in whitelist:
                    raise InvalidParameterSyntax(
                        "'*' cannot be used with other rule names in the use directive"
                    )
                if not all(is_identifier(name) for name in whitelist):
                    fail()
            if tokens[i] not in ("from", "as", "with", "with:"):
                fail()

            # module: the source after `from`
            if tokens[i] == "from":
                i += 1
                module = tokens[i]
                if not is_identifier(module):
                    fail()
                i += 1
            else:
                module = None
        except IndexError:
            fail()

        # exclude: comma separated rule names after `exclude`
        token_length = len(tokens)
        exclude: list[str] = []
        rename = None
        try:
            # exclude: comma separated rule names after `exclude`
            if i < token_length and tokens[i] == "exclude":
                exclude.append(tokens[i + 1])
                i += 2
                while i < token_length and tokens[i] == ",":
                    exclude.append(tokens[i + 1])
                    i += 2
                if not all(is_identifier(name) for name in exclude):
                    fail()
            # modifier: the alias after `as`
            if i < token_length and tokens[i] == "as":
                rename = tokens[i + 1]
                if not is_glob(rename):
                    fail()
                i += 2
        except IndexError:
            fail()

        if "".join(tokens[i:]) not in ("", "with:"):
            fail()

        if module is None and rename is None:
            raise InvalidParameterSyntax(
                "use directive must specify a rule from a module or modify the rule"
            )

        self.whitelist = whitelist
        self.module = module
        self.exclude = exclude
        self.rename = rename

    def consume_body(self, tokens):
        super().consume_body(tokens)
        for block in self.body_blocks:
            if isinstance(block, SnakemakeArgumentsBlock):
                body = block.colon_line.body
                # nameable children here take `with`, nothing else
                if not _is_op(":", body[1]) and body[1].string != "with":
                    ColonError(_line_nb(body[1]), body[1].string, body[0].string)

    def formatted(self, mode, state):
        """Allow:
        use rule * from other_workflow exclude ruleC as other_*
        use rule * from other_workflow exclude ruleC
        use rule * from other_workflow as other_*
        use rule * from other_workflow
        use rule a,b from other_workflow
        """
        assert len(self.head_lines) == 1, "use directive should only have one head line"
        head_line = tokens2linestrs(iter(self.head_lines[0].body))
        assert len(head_line) == 1, "use directive should be single line"
        head_bulk_line = head_line[0].split("#", 1)[0]
        if ":" not in head_bulk_line:
            # return quickly (also no body block here)
            indent = TAB * self.deindent_level
            components = head_bulk_line.strip().split()
            formatted_head = indent + " ".join(components)
            if "#" in head_line[0]:
                formatted_head += "  " + format_black(
                    "#" + head_line[0].split("#", 1)[1], mode=mode
                ).rstrip("\n")
            return formatted_head + "\n"
        formatted_prior, post_colon = self.format_head(mode)
        formatted_body = self.format_body(mode, state, post_colon)
        formatted = [formatted_prior, formatted_body]
        return "".join(formatted)

    subautomata = {**_Rule.subautomata} | {
        keyword: type(keyword, (_Rule.subautomata[keyword],), {"nameable": True})
        for keyword in (
            "input",
            "output",
            "log",
            "pathvars",
            "wildcard_constraints",
            "resources",
            "params",
        )
    }


@_register()
class Rule(_Rule):
    # Action
    exec_subautomata, _register = init_block_register()

    @_register()
    class Run(SnakemakeExecutableBlock): ...

    class AbstractCmd(SnakemakeUnnamedArgumentBlock, Run): ...

    @_register()
    class Shell(AbstractCmd):
        def format_body(
            self, mode: Mode, state: FormatState, post_colon: list[TokenInfo]
        ) -> str:
            """Format the body, then (if enabled) reformat its lone string
            literal as shell code with `shfmt`.

            Going through the normal body formatting first keeps surrounding
            comments/blank lines and the trailing-comma handling; only the
            literal itself is then swapped for its `shfmt`'ed form.
            """
            formatted = super().format_body(mode, state, post_colon)
            if not state.format_shell:
                return formatted
            strings = [
                token
                for token in tokenize.generate_tokens(io.StringIO(formatted).readline)
                if token.type == tokenize.STRING
            ]
            if len(strings) != 1:
                return formatted
            (string,) = strings
            lines = formatted.splitlines(keepends=True)
            start = (
                sum(len(line) for line in lines[: string.start[0] - 1])
                + string.start[1]
            )
            end = sum(len(line) for line in lines[: string.end[0] - 1]) + string.end[1]
            return (
                formatted[:start]
                + format_python_string_literal(
                    formatted[start:end], self.deindent_level + 1
                )
                + formatted[end:]
            )

    @_register()
    class Script(AbstractCmd): ...

    @_register()
    class Notebook(Script): ...

    @_register()
    class Wrapper(Script): ...

    @_register()
    class CWL(Script): ...

    @_register("template_engine")
    class TemplateEngine(Script): ...

    subautomata = {**_Rule.subautomata, **exec_subautomata}


@_register()
class Checkpoint(Rule): ...


class GlobalBlock(Block):
    """Hold `body_blocks` only, no `head_lines` nor `tail_noncoding`

    all blocks in `body_blocks` should in the
      same deindent level as GlobalBlock itself
    so tail_noncoding always updated to the last body_block
    """

    __slots__ = ("mode", "state")
    mode: Mode
    state: FormatState

    subautomata = {**python_subautomata, **global_snakemake_subautomata}

    def __init__(self, deindent_level, tokens, lines=None):
        super().__init__(deindent_level, tokens, lines)

    def consume(self, tokens):
        self.body_blocks = self.consume_subblocks(tokens)

    def get_formatted(self, mode: Mode | None = None):
        if mode is None:
            mode = getattr(self, "mode", None)
            if mode is None:
                raise ValueError("Mode should be provided for formatting")
        state = getattr(self, "state", None)
        if state is None:
            state = FormatState()
        # if set to None, it will not be enabled by `# fmt: on`
        python_codes: list[str] = []
        snakemake_codes: list[tuple[str, str]] = []
        last_str = ""
        for segment, indent_proxy in self.segment2format(mode, state):
            if indent_proxy is not None:
                python_codes.append(last_str)
                last_str = ""
                snakemake_codes.append((segment, indent_proxy))
            else:
                last_str += segment
        placeholder = "o" * 50
        raw_str = "".join(python_codes)
        while placeholder in raw_str:
            placeholder *= 2
        raw_str = "#\n"
        for python_code, (snakemake_code, indent) in zip(python_codes, snakemake_codes):
            if snakemake_code.count("\n") == 1:  # must at the end of line
                snakemake_proxy = f"{indent}def l{placeholder}1ng(): ...\n"
            else:
                snakemake_proxy = f"{indent}def l{placeholder}ng():\n{indent} return\n"
            raw_str += python_code + snakemake_proxy
        raw_str += last_str
        formatted, *formatted_split = format_black(raw_str, mode).split(placeholder)
        final_str = formatted
        for formatted, (snakemake_code, _) in zip(formatted_split, snakemake_codes):
            final_str = final_str.rsplit("\n", 1)[0] + "\n" + snakemake_code
            if formatted.startswith("1"):
                final_str += formatted.split("\n", 1)[-1]
            else:
                final_str += formatted.split("\n", 2)[-1]
        return final_str[1:].lstrip("\n")

    def compilation(self):
        raise NotImplementedError


def parse(source: str | Callable[[], str], name: str = "<string>"):
    if isinstance(source, str):
        tokens = tokenize.generate_tokens(
            iter(source.splitlines(keepends=True)).__next__
        )
    else:
        tokens = tokenize.generate_tokens(source)
    return GlobalBlock(0, TokenIterator(name, tokens), [])


def setup_formatter(
    snake: str,
    line_length: int | None = None,
    sort_directives: bool = False,
    black_config_file=None,
    format_shell=False,
    directive_order: tuple[str, ...] = (),
    module_directive_order: tuple[str, ...] = (),
):
    formatter = parse(snake)
    mode = read_black_config(black_config_file) or Mode()
    if line_length is not None:
        mode.line_length = line_length

    formatter.mode = mode
    formatter.state = FormatState(
        sort_directives=sort_directives,
        format_shell=format_shell,
        rule_order=tuple(directive_order),
        module_order=tuple(module_directive_order),
    )
    return formatter
