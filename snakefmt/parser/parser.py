import tokenize
from abc import ABC, abstractmethod
from typing import NamedTuple, Optional

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


def not_a_comment_related_token(token: Token):
    return token.type not in {
        tokenize.COMMENT,
        tokenize.NEWLINE,
        tokenize.NL,
        tokenize.INDENT,
        tokenize.DEDENT,
    }


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

            if self.vocab.recognises(keyword):
                if status.cur_indent > self.keyword_indent:
                    in_if_else = self.buffer.startswith(("if", "else", "elif"))
                    if self.syntax.from_python or status.pythonable or in_if_else:
                        self.from_python = True
                elif self.from_python:
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
            else:
                if not self.syntax.accepts_python_code and not comment_start(keyword):
                    raise SyntaxError(
                        f"L{status.token.start[0]}: Unrecognised keyword '{keyword}' "
                        f"in {self.syntax.keyword_name} definition"
                    )
                else:
                    self.buffer += f"{keyword}"
                    status = self.get_next_queriable()
                    if self.last_block_was_snakecode and not status.eof:
                        self.block_indent = status.block_indent
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
            return Status(
                param_context.token,
                param_context.cur_indent,
                param_context.cur_indent,
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
                self.flush_buffer()  # Flushes any code inside 'run' directive
            else:
                callback_context.syntax.check_empty()
            self.context = self.context_stack[-1]

        self.syntax.from_python = callback_context.syntax.from_python
        self.syntax.cur_indent = status.cur_indent
        self.block_indent = self.cur_indent
        if self.keyword_indent > 0:
            self.syntax.keyword_indent = status.cur_indent + 1

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
            if token.type == tokenize.INDENT:
                self.syntax.cur_indent += 1
                prev_token = None
                newline = True
                continue
            elif token.type == tokenize.DEDENT:
                if self.cur_indent > 0:
                    self.syntax.cur_indent -= 1
                prev_token = None
                newline = True
                continue
            elif token.type == tokenize.ENDMARKER:
                return Status(
                    token, block_indent, self.cur_indent, buffer, True, pythonable
                )
            elif token.type == tokenize.COMMENT:
                if col_nb(token) == 0:
                    return Status(token, block_indent, 0, buffer, False, pythonable)

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

            if (token.type == tokenize.NAME or token.string == "@") and self.queriable:
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
