import re
import tokenize
from abc import ABC, abstractmethod
from typing import Literal, NamedTuple, Optional

from snakefmt.exceptions import UnsupportedSyntax
from snakefmt.parser.grammar import PythonCode, SnakeGlobal
from snakefmt.parser.syntax import (
    KeywordSyntax,
    ParameterSyntax,
    Vocabulary,
    add_token_space,
    fstring_processing,
    is_newline,
    re_add_curly_bracket_if_needed,
)
from snakefmt.types import TAB, Token, TokenIterator, col_nb

_FMT_DIRECTIVE_RE = re.compile(
    r"^# fmt: (off|on)(?:\[(\w+(?:,\s*\w+)*)\])?(?=$|\s{2}|\s#)"
)


class FMT_DIRECTIVE(NamedTuple):
    disable: bool
    modifiers: list[str]

    @classmethod
    def from_token(cls, token: Token):
        if token.type != tokenize.COMMENT:
            return None
        return cls.from_str(token.string)

    @classmethod
    def from_str(cls, token_string: str):
        """Parse a fmt directive comment.
        Returns (disable, modifiers) or None if not a fmt directive.
        disable:   True | False
        modifiers: e.g. [] | ['sort'] | ['next'] | ['sort', 'next']
        """
        m = _FMT_DIRECTIVE_RE.match(token_string)
        if m is None:
            return None
        disable = m.group(1) == "off"
        mods = [s.strip() for s in m.group(2).split(",")] if m.group(2) else []
        return cls(disable, mods)  # type: ignore[arg-type]


def split_token_lines(token: tokenize.TokenInfo):
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


def not_a_comment_related_token(token: Token):
    return token.type not in {
        tokenize.COMMENT,
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.INDENT,
        tokenize.DEDENT,
    }


def check_indent(line: str, indents: list[str]) -> int:
    indents_len = len(indents)
    for i, indent in enumerate(reversed(indents), 1):
        if line.startswith(indent):
            return indents_len - i
    raise SyntaxError("Unexpected indent")


class Snakefile(TokenIterator):
    """
    Adapted from snakemake.parser.Snakefile
    """

    def __init__(self, fpath_or_stream, rulecount=0):
        try:
            self.stream = open(fpath_or_stream, encoding="utf-8")
        except TypeError:
            self.stream = fpath_or_stream

        self._live_tokens = tokenize.generate_tokens(self.stream.readline)
        self._buffered_tokens = list()
        self.rulecount = rulecount
        self.lines = 0

    def __next__(self) -> Token:
        if self._buffered_tokens:
            return self._buffered_tokens.pop()
        return next(self._live_tokens)

    def denext(self, token: Token) -> None:
        self._buffered_tokens.append(token)


def comment_start(string: str) -> bool:
    return string.lstrip().startswith("#")


class Status(NamedTuple):
    """Communicates the result of parsing a chunk of code"""

    token: Token
    block_indent: int  # indent of the start of the parsed block
    cur_indent: int  # indent of the end of the parsed block
    buffer: str
    eof: bool
    pythonable: bool


class Context(NamedTuple):
    """
    Ties together a vocabulary and a syntax.
    When a keyword from `vocab` is recognised, a new context is induced
    """

    vocab: Vocabulary
    syntax: KeywordSyntax


class Parser(ABC):
    """
    The parser alternates between parsing blocks of python code (`pycode`) and
    blocks of snakemake code (`snakecode`).
    The indentation of these code blocks is memorised in :`self.block_indent`,
    and the alternation in `:self.last_block_was_snakecode`.
    """

    def __init__(self, snakefile: Snakefile):
        self.context = Context(
            SnakeGlobal(), KeywordSyntax("Global", keyword_indent=0, accepts_py=True)
        )
        self.context_stack = [self.context]
        self.snakefile = snakefile
        self.from_python: bool = False
        self.last_recognised_keyword: str = ""
        self.last_block_was_snakecode = False
        self.block_indent = 0
        self.queriable = True
        self.in_fstring = False
        self.last_token: Optional[Token] = None
        self.fmt_sort_off: Optional[int]
        # for `# fmt: off`, (indent, kind)
        # kind: "region" = off/on, "sort" = off[sort]/on[sort], "next"
        self.fmt_off: Optional[tuple[int, Literal["next", "region"]]] = None
        self.fmt_off_expected_index: str = ""
        self.fmt_off_preceded_by_blank_line: bool = False

        self.indents: list[str] = [""]

        status = self.get_next_queriable()
        self.buffer = status.buffer

        # Parse the full snakemake file
        while True:
            if status.cur_indent < self.keyword_indent:
                self.context_exit(status)
                self.post_process_keyword()

            if status.eof:
                self.post_process_keyword()
                break

            keyword = status.token.string
            if fmt_label := FMT_DIRECTIVE.from_token(status.token):
                if fmt_label.disable:
                    if not fmt_label.modifiers:
                        self.fmt_off = (status.cur_indent, "region")
                        self.fmt_off_expected_index = status.token.line[
                            : col_nb(status.token)
                        ]
                    elif "next" in fmt_label.modifiers:
                        self.fmt_off = (status.cur_indent, "next")
                        self.fmt_off_expected_index = status.token.line[
                            : col_nb(status.token)
                        ]
                    elif "sort" in fmt_label.modifiers:
                        self.fmt_sort_off = status.cur_indent
                elif self._check_fmt_on(fmt_label, status.token) == "sort":
                    continue
            elif self.fmt_off and status.cur_indent <= self.fmt_off[0]:
                self.fmt_off = None
            elif (
                self.fmt_sort_off is not None and status.cur_indent < self.fmt_sort_off
            ):
                self.fmt_sort_off = None

            if self.vocab.recognises(keyword):
                new_vocab, new_syntax_cls = self.vocab.get(keyword)
                is_context_kw = new_vocab is not None and issubclass(
                    new_syntax_cls, KeywordSyntax
                )
                if status.cur_indent > self.keyword_indent:
                    if self.syntax.from_python or status.pythonable:
                        self.from_python = True
                elif self.from_python and not is_context_kw:
                    # We are exiting python context, so force spacing out keywords
                    self.last_recognised_keyword = ""
                    self.from_python = self.syntax.from_python
                self.flush_buffer(
                    from_python=self.from_python,
                    in_global_context=self.in_global_context,
                )
                status = self.process_keyword(status, self.from_python)
                self.block_indent = status.cur_indent
                self.last_block_was_snakecode = True
            elif self.fmt_off:
                self.flush_buffer(
                    from_python=True,
                    in_global_context=self.in_global_context,
                )
                if self.keyword_indent > 0:
                    self.syntax.add_processed_keyword(status.token, keyword)
                status = self._consume_fmt_off(
                    status.token, min_indent=status.cur_indent
                )
                self.buffer = ""
                if self.last_block_was_snakecode and not status.eof:
                    self.block_indent = status.block_indent
                    self.last_block_was_snakecode = False
                if self.keyword_indent:
                    self.last_block_was_snakecode = True
                self.buffer = status.buffer.lstrip()
            else:
                if not self.syntax.accepts_python_code and not comment_start(keyword):
                    raise SyntaxError(
                        f"L{status.token.start[0]}: Unrecognised keyword '{keyword}' "
                        f"in {self.syntax.keyword_name} definition"
                    )
                else:
                    source, status = self._consume_python(status.token)
                    self.buffer += source
                    if self.last_block_was_snakecode and not status.eof:
                        self.last_block_was_snakecode = False
                    self.buffer += status.buffer
                    if (
                        self.from_python
                        and status.cur_indent == 0
                        and not self.last_block_was_snakecode
                        and self.block_indent > 0
                    ):
                        # This flushes any nested python code following a
                        # nested snakemake keyword
                        self.flush_buffer(
                            from_python=True, in_global_context=self.in_global_context
                        )
                        self.from_python = False
                        self.block_indent = status.cur_indent
            if not comment_start(keyword):
                self.syntax.cur_indent = status.cur_indent
        self.flush_buffer(
            from_python=self.from_python,
            final_flush=True,
            in_global_context=self.in_global_context,
        )

    @property
    def vocab(self) -> Vocabulary:
        return self.context.vocab

    @property
    def syntax(self) -> KeywordSyntax:
        return self.context.syntax

    @property
    def keyword_indent(self) -> int:
        return self.syntax.keyword_indent

    @property
    def cur_indent(self) -> int:
        return self.syntax.cur_indent

    @property
    def in_global_context(self) -> bool:
        return self.vocab.__class__ is SnakeGlobal

    @property
    def effective_indent(self) -> int:
        return max(0, self.cur_indent - max(0, self.block_indent))

    @abstractmethod
    def flush_buffer(
        self,
        from_python: bool = False,
        final_flush: bool = False,
        in_global_context: bool = False,
        exiting_keywords: bool = False,
    ) -> None:
        """Processes the text in :self.buffer:"""

    @abstractmethod
    def process_keyword_context(self, in_global_context: bool):
        """Initialises parsing a keyword context, eg a 'rule:'"""

    @abstractmethod
    def process_keyword_param(
        self, param_context: ParameterSyntax, in_global_context: bool
    ):
        """Initialises parsing a keyword parameter, eg a 'input:'"""

    @abstractmethod
    def post_process_keyword(self) -> None:
        """Sort params when exiting a keyword context,
        eg after finishing parsing a 'rule:'"""

    def _consume_python(
        self, start_token: Token, vocab_recognises=True, added_indent: str = ""
    ) -> tuple[str, Status]:
        """Collect Python source lines until a snakemake keyword at correct indent,
        or dedent below min_indent, or EOF.
        Returns (source_text, next_status) where next_status carries the stopping token.
        """
        origin_indent = start_token.start[1]

        lines: dict[int, str] = {start_token.start[0]: start_token.line}
        # Lines that are interior to a multiline token (string / f-string body).
        # Their content must not be reindented.
        string_interior_lines: set[int] = set()
        self.queriable = False
        prev_token = None
        last_indent_token = None
        min_indent = -1
        # If stop_at_min is True, also stop when dedenting back to min_indent level
        # (used for fmt: off[next] to consume exactly one block).
        is_next_mode = self.fmt_off and self.fmt_off[1] == "next"
        consuming_next = False  # used with stop_at_min
        seen_next_block_keyword = False

        def _init_min_indent(token: Token):
            nonlocal min_indent
            if not comment_start(token.string):
                while not token.line.startswith(self.indents[-1]):
                    self.indents.pop()
                min_indent = len(self.indents) - 1

        _init_min_indent(start_token)
        while True:
            try:
                token = next(self.snakefile)
            except StopIteration:
                eof_token = Token(tokenize.ENDMARKER, "", (0, 0), (0, 0), "")
                self.snakefile.denext(eof_token)
                break
            if min_indent == -1:
                _init_min_indent(token)
            elif token.line[:origin_indent].strip():
                # non-whitespace before origin indent: stop
                self.snakefile.denext(token)
                break
            self.last_token = token
            self.in_fstring = fstring_processing(token, prev_token, self.in_fstring)
            prev_token = token
            if token.type == tokenize.ENDMARKER:
                self.snakefile.denext(token)
                break
            elif token.type == tokenize.INDENT:
                self._handle_indent(token)
                self.syntax.cur_indent = len(self.indents) - 1
                last_indent_token = token
                if is_next_mode and len(self.indents) - 1 > min_indent:
                    consuming_next = True
                continue
            elif token.type == tokenize.DEDENT:
                saved_indents = list(self.indents)
                self._handle_indent(token)
                new_indent = len(self.indents) - 1
                last_indent_token = None
                if new_indent < min_indent or (
                    consuming_next and new_indent == min_indent
                ):
                    # let get_next_queriable handle dedent below min_indent
                    self.indents = saved_indents
                    self.snakefile.denext(token)
                    break
                self.syntax.cur_indent = new_indent
                continue
            elif is_newline(token):
                self.queriable = True
                lines.update(split_token_lines(token))
                continue
            elif (
                (token.type == tokenize.NAME or token.string == "@")
                and self.queriable
                and not self.in_fstring
                and self.vocab.recognises(token.string)
            ):
                if is_next_mode:
                    if seen_next_block_keyword:
                        # fmt: off[next] consumed one whole keyword block;
                        # hand the next same-level block back to main loop.
                        self.snakefile.denext(token)
                        if last_indent_token is not None:
                            self.snakefile.denext(last_indent_token)
                            self.indents.pop()
                            self.syntax.cur_indent = len(self.indents) - 1
                        break
                    else:
                        seen_next_block_keyword = True
                if vocab_recognises:
                    # snakemake keyword: stop, let main loop handle it
                    self.snakefile.denext(token)
                    if last_indent_token is not None:
                        self.snakefile.denext(last_indent_token)
                        self.indents.pop()
                        self.syntax.cur_indent = len(self.indents) - 1
                    break
            # `# fmt: off[next]` within Python code: stop and let main loop handle it.
            elif fmt_label := FMT_DIRECTIVE.from_token(token):
                if fmt_label.disable:
                    if fmt_label.modifiers:
                        # `# fmt: off[` is not actual format diabler, it affects limited
                        if not self.fmt_off or (
                            # two following [next]
                            self.fmt_off[1] != "region"
                            and self._determe_comment_indent(token) == self.fmt_off[0]
                        ):
                            self.snakefile.denext(token)
                            break
                    elif self.in_global_context:
                        # In global Python context, plain `# fmt: off` starts a parser
                        # verbatim region. In non-global Python contexts (e.g. run:), it
                        # stays inside Python and is handled by Black.
                        last_line = lines[max(lines)] if lines else ""
                        self.fmt_off_preceded_by_blank_line = not last_line.strip()
                        self.snakefile.denext(token)
                        break
                elif fmt_on := self._check_fmt_on(fmt_label, token):
                    if fmt_on == "region":
                        lines.update(split_token_lines(token))
                    break

            self.queriable = False
            lines.update(split_token_lines(token))
            # Mark interior lines of any multiline token as string content.
            if token.start[0] != token.end[0]:
                string_interior_lines.update(
                    range(token.start[0] + 1, token.end[0] + 1)
                )

        verbatim = self._reindent(
            lines, string_interior_lines, origin_indent, added_indent
        )
        next_status = self.get_next_queriable()
        if consuming_next and verbatim:
            # Strip extra trailing blank lines; the following block's separator
            # logic (add_newlines) will provide the correct spacing.
            while verbatim.endswith("\n\n"):
                verbatim = verbatim[:-1]
        return verbatim, next_status._replace(
            pythonable=next_status.pythonable or bool(verbatim.strip())
        )

    @abstractmethod
    def handle_fmt_off_region(self, verbatim: str) -> None:
        """handle unformatted text (just update indent)."""

    def _consume_fmt_off(self, start_token: Token, min_indent: int):
        verbatim, next_status = self._consume_python(
            start_token, vocab_recognises=False, added_indent=TAB * min_indent
        )
        self.handle_fmt_off_region(verbatim)
        self.snakefile.denext(next_status.token)
        self.queriable = True
        if self.fmt_off and self.fmt_off[1] == "next":
            self.fmt_off = None
        return self.get_next_queriable()

    def _reindent(
        self,
        lines: dict[int, str],
        string_interior_lines: set[int],
        origin_indent: int,
        added_indent: str = "",
    ) -> str:
        newlines = []
        for i in sorted(lines):
            line = lines[i]
            if i in string_interior_lines:
                newlines.append(line)
            elif line.strip():
                newline = line.rsplit("\n", 1)
                if newline[0][:origin_indent].strip():
                    newline[0] = added_indent + newline[0].lstrip()
                else:
                    newline[0] = added_indent + newline[0][origin_indent:]
                newlines.append("\n".join(newline))
            else:
                newlines.append(line[origin_indent:])
        return "".join(newlines)

    def process_keyword(self, status: Status, from_python: bool = False) -> Status:
        """Called when a snakemake keyword has been found.

        The function dispatches to processing class for either:
            - keyword context: can accept more keywords, eg 'rule'
            - keyword parameter: accepts parameter value, eg 'input'
        """
        keyword = status.token.string
        new_vocab, new_syntax = self.vocab.get(keyword)
        if new_vocab is not None and issubclass(new_syntax, KeywordSyntax):
            in_global_context = self.in_global_context
            saved_context = self.context
            # 'use' keyword can not enter a new context
            self.context = Context(
                new_vocab(),
                new_syntax(
                    keyword,
                    self.syntax.cur_indent + 1,
                    snakefile=self.snakefile,
                    incident_syntax=self.syntax,
                    from_python=from_python,
                    accepts_py=new_vocab is PythonCode,
                ),
            )
            self.process_keyword_context(in_global_context)
            if self.syntax.enter_context:
                self.context_stack.append(self.context)
            else:
                self.context = saved_context

            self.queriable = True
            self.block_indent = self.syntax.keyword_indent + 1
            status = self.get_next_queriable()
            # lstrip forces the formatter deal with newlines
            if self.context.syntax.accepts_python_code:  # type: ignore
                self.buffer += status.buffer.lstrip("\n\r")
            else:
                self.buffer += status.buffer.lstrip()
            return status

        elif issubclass(new_syntax, ParameterSyntax):
            param_context = new_syntax(
                keyword,
                self.syntax.cur_indent + 1,
                self.vocab,
                self.snakefile,
                allow_with=self.syntax.keyword_name == "use",
            )
            self.process_keyword_param(param_context, self.in_global_context)
            self.syntax.add_processed_keyword(status.token, status.token.string)
            cur_indent = param_context.cur_indent
            if param_context.token.type == tokenize.COMMENT and not param_context.eof:
                cur_indent = self._determe_comment_indent(param_context.token)
            return Status(
                param_context.token,
                cur_indent,
                cur_indent,
                status.buffer,
                param_context.eof,
                self.from_python,
            )

        else:
            raise UnsupportedSyntax()

    def context_exit(self, status: Status) -> None:
        """Parser leaves a keyword context, for eg from 'rule:' to python code"""
        while self.keyword_indent > status.cur_indent:
            callback_context: Context = self.context_stack.pop()
            if callback_context.syntax.accepts_python_code:
                # Flushes any code inside 'run' directive
                self.flush_buffer(exiting_keywords=True)
            else:
                callback_context.syntax.check_empty()
            self.context = self.context_stack[-1]

        self.syntax.from_python = callback_context.syntax.from_python
        self.syntax.cur_indent = status.cur_indent
        self.block_indent = self.cur_indent
        if self.keyword_indent > 0:
            self.syntax.keyword_indent = status.cur_indent + 1
        # ParameterSyntax consumes INDENT/DEDENT tokens without updating
        # Parser.indents, leaving stale deeper-level entries. Trim them now
        # so get_next_queriable computes the correct cur_indent for the next block.
        while len(self.indents) - 1 > status.cur_indent:
            self.indents.pop()

    def _determe_comment_indent(self, token: Token) -> int:
        """
        Treat each line of single-line comment separately,
        it is determined by the following real code line and previous self.indents.

        follow_indent = indent of the following real code line
        if EOF:
            follow_indent = 0
        rule 1 (always):
            indent of comments >= follow_indent
        rule 2 (if follow_indent < self.indents[-1]):
            indent of comments = max(i for i in self.indents
                                     if i <= comment_indent) + epsilon.

        next(self.snakefile) until follow_indent is determined,
        then put all peeked tokens back.
        """
        # ── Step 1: peek ahead to find follow_indent ────────────────────────
        peeked: list[Token] = []
        saved_indents = list(self.indents)
        follow_indent = len(self.indents) - 1
        try:
            while True:
                t = next(self.snakefile)
                peeked.append(t)
                if self._handle_indent(t):
                    pass
                elif t.type not in {tokenize.NEWLINE, tokenize.NL, tokenize.COMMENT}:
                    follow_indent = check_indent(t.line, self.indents)
                    break
        except StopIteration:
            follow_indent = 0
        # restore indent stack and token stream unchanged
        self.indents = saved_indents
        for t in reversed(peeked):
            self.snakefile.denext(t)

        # Rule 1 (always): comment must not be indented below following code.
        if len(self.indents) - 1 <= follow_indent:
            return follow_indent
        # Rule 2 (dedent is happening, standalone only): snap comment to the
        # highest indent level fitting within the comment's column.
        return max(check_indent(token.line, self.indents), follow_indent)

    def _check_fmt_on(self, fmt_label: FMT_DIRECTIVE, token: Token):
        """Return True if token ends the current fmt:off region."""
        if self.fmt_off:
            # `# fmt: on[sort]` no effect
            if "sort" not in fmt_label.modifiers:
                token_indent = self._determe_comment_indent(token)
                if token_indent == self.fmt_off[0]:
                    self.fmt_off = None
                    return "region"
        elif self.fmt_sort_off is not None:
            if "sort" in (fmt_label.modifiers or ["sort"]):
                token_indent = self._determe_comment_indent(token)
                if token_indent == self.fmt_sort_off:
                    self.fmt_sort_off = None
                    return "sort"

    def _handle_indent(self, token: Token) -> bool:
        if token.type == tokenize.INDENT:
            line = token.line
            indent = line[: len(line) - len(line.lstrip())]
            if indent not in self.indents:
                self.indents.append(indent)
        elif token.type == tokenize.DEDENT:
            line = token.line
            indent = line[: len(line) - len(line.lstrip())]
            while self.indents and self.indents[-1] != indent:
                self.indents.pop()
            if not self.indents:
                raise SyntaxError("Unexpected dedent")
        else:
            return False
        return True

    def get_next_queriable(self) -> Status:
        """Produces the next word that could be a snakemake keyword,
        and additional information in a :Status:

        Note: comments are annoying, as when preceded by indents/dedents,
        they are output by the tokenizer before those indents/dedents.
        """
        buffer = ""
        newline = False
        pythonable = False
        block_indent = -1
        prev_token: Optional[Token] = Token(tokenize.NAME, "", (-1, -1), (-1, -1), "")
        while True:
            token = next(self.snakefile)
            self.last_token = token
            self.in_fstring = fstring_processing(token, prev_token, self.in_fstring)
            if block_indent == -1 and not_a_comment_related_token(token):
                block_indent = self.cur_indent
            if self._handle_indent(token):
                prev_token = None
                newline = True
                self.syntax.cur_indent = len(self.indents) - 1
                continue
            elif token.type == tokenize.ENDMARKER:
                return Status(
                    token, block_indent, self.cur_indent, buffer, True, pythonable
                )
            elif token.type == tokenize.COMMENT:
                fmt_dir = FMT_DIRECTIVE.from_token(token)
                if (
                    fmt_dir
                    and col_nb(token) == 0
                    and not (fmt_dir.disable and "next" in (fmt_dir.modifiers or []))
                ):
                    # col-0 comments report cur_indent=0 to trigger context_exit;
                    # fmt directives at other columns report actual cur_indent.
                    return Status(token, block_indent, 0, buffer, False, pythonable)
                # Comments arrive in the token stream *before* any following
                # INDENT/DEDENT tokens, so self.cur_indent still reflects the
                # previous (potentially higher) level.  Delegate to
                # _determe_comment_indent which peeks ahead and applies the
                # two snapping rules.
                effective_indent = self._determe_comment_indent(token)
                self.syntax.cur_indent = effective_indent
                if effective_indent < max(self.keyword_indent, self.block_indent):
                    return Status(
                        token, block_indent, effective_indent, buffer, False, pythonable
                    )
                # `# fmt: off[next]` always needs parser-level handling.
                # Plain `# fmt: off` is parser-level only in global context; in other
                # Python contexts it is handled by Black.
                if (
                    fmt_dir
                    and fmt_dir.disable
                    and (
                        "next" in fmt_dir.modifiers
                        or "sort" in fmt_dir.modifiers
                        or (not fmt_dir.modifiers and self.in_global_context)
                    )
                ):
                    return Status(
                        token, block_indent, effective_indent, buffer, False, pythonable
                    )

            elif is_newline(token):
                self.queriable, newline = True, True
                buffer += "\n"
                prev_token = None
                continue

            # Records relative tabbing, used for python code formatting
            if newline:
                if token.type == tokenize.COMMENT:
                    # Because comment indent level is not knowable from indent/dedent
                    # tokens, just use its input whitespace level.
                    # We subtract the block indent, as it is added back by the formatter
                    indent = max(0, col_nb(token) - (self.block_indent * len(TAB)))
                    buffer += " " * indent
                else:
                    buffer += TAB * self.effective_indent

            if (
                (token.type == tokenize.NAME or token.string == "@")
                and self.queriable
                and not self.in_fstring
            ):
                self.queriable = False
                return Status(
                    token, block_indent, self.cur_indent, buffer, False, pythonable
                )

            if add_token_space(prev_token, token, self.in_fstring):
                buffer += " "
            prev_token = token
            if newline:
                newline = False
            if not pythonable and token.type != tokenize.COMMENT:
                pythonable = True
            buffer += token.string
            buffer += re_add_curly_bracket_if_needed(token)
