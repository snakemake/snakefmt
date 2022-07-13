import tokenize
from abc import ABC, abstractmethod

from snakefmt.exceptions import UnsupportedSyntax
from snakefmt.parser.grammar import Context, PythonCode, SnakeGlobal
from snakefmt.parser.syntax import KeywordSyntax, ParameterSyntax, Syntax, Vocabulary
from snakefmt.types import Token, TokenIterator


class Snakefile:
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
        if len(self._buffered_tokens) == 0:
            return next(self._live_tokens)
        else:
            return self._buffered_tokens.pop()

    def denext(self, token: Token) -> None:
        self._buffered_tokens.append(token)


def comment_start(string: str) -> bool:
    return string.lstrip().startswith("#")


class Parser(ABC):
    def __init__(self, snakefile: TokenIterator):
        self.context = Context(
            SnakeGlobal(), KeywordSyntax("Global", target_indent=0, accepts_py=True)
        )
        self.context_stack = [self.context]
        self.snakefile: TokenIterator = snakefile
        self.from_python: bool = False
        self.last_recognised_keyword: str = ""
        self.last_line_is_snakecode = False

        status = self.syntax.get_next_queriable(self.snakefile)
        self.buffer = status.buffer

        # Parse the full snakemake file
        while True:
            if status.indent < self.target_indent:
                self.context_exit(status)

            if status.eof:
                break

            keyword = status.token.string

            if self.vocab.recognises(keyword):
                if status.indent > self.target_indent:
                    if self.syntax.from_python or status.pythonable:
                        self.from_python = True
                    else:  # Over-indented context gets reset
                        self.syntax.cur_indent = max(self.target_indent - 1, 0)
                elif self.from_python:
                    # We are exiting python context, so force spacing out keywords
                    self.last_recognised_keyword = ""
                self.flush_buffer(
                    from_python=self.from_python,
                    in_global_context=self.in_global_context,
                )
                self.syntax.code_indent = None
                status = self.process_keyword(status, self.from_python)
                self.last_line_is_snakecode = True
            else:
                if not self.syntax.accepts_python_code and not comment_start(keyword):
                    raise SyntaxError(
                        f"L{status.token.start[0]}: Unrecognised keyword '{keyword}' "
                        f"in {self.syntax.keyword_name} definition"
                    )
                else:
                    self.buffer += keyword
                    if self.syntax.code_indent is None and not comment_start(keyword):
                        # This allows python code after a nested snakemake keyword
                        # to be properly indented
                        self.syntax.code_indent = status.indent
                    status = self.syntax.get_next_queriable(self.snakefile)
                    self.buffer += status.buffer
                    if (
                        self.from_python
                        and status.indent == 0
                        and not self.last_line_is_snakecode
                    ):
                        # This flushes any nested python code following a
                        # nested snakemake keyword
                        self.flush_buffer(
                            from_python=True, in_global_context=self.in_global_context
                        )
                        self.from_python = False
                self.last_line_is_snakecode = False
            self.syntax.cur_indent = status.indent
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
    def target_indent(self) -> int:
        return self.syntax.target_indent

    @property
    def in_global_context(self) -> bool:
        return self.vocab.__class__ is SnakeGlobal

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

    def process_keyword(
        self, status: Syntax.Status, from_python: bool = False
    ) -> Syntax.Status:
        """Called when a snakemake keyword has been found.

        The function dispatches to processing class for either:
            - keyword context: can accept more keywords, eg 'rule'
            - keyword parameter: accepts parameter value, eg 'input'
        """
        keyword = status.token.string
        new_context = self.vocab.get(keyword)
        accepts_py = new_context.vocab is PythonCode
        if issubclass(new_context.syntax, KeywordSyntax):
            in_global_context = self.in_global_context
            saved_context = self.context
            # 'use' keyword can not enter a new context
            self.context = Context(
                new_context.vocab(),
                new_context.syntax(
                    keyword,
                    self.syntax.cur_indent + 1,
                    snakefile=self.snakefile,
                    incident_syntax=self.syntax,
                    from_python=from_python,
                    accepts_py=accepts_py,
                ),
            )
            self.process_keyword_context(in_global_context)
            if self.syntax.enter_context:
                self.context_stack.append(self.context)
            else:
                self.context = saved_context

            status = self.syntax.get_next_queriable(self.snakefile)
            # lstrip forces the formatter deal with newlines
            self.buffer += status.buffer.lstrip()
            return status

        elif issubclass(new_context.syntax, ParameterSyntax):
            param_context = new_context.syntax(
                keyword, self.syntax.cur_indent + 1, self.vocab, self.snakefile
            )
            self.process_keyword_param(param_context, self.in_global_context)
            self.syntax.add_processed_keyword(status.token, status.token.string)
            return Syntax.Status(
                param_context.token,
                param_context.cur_indent,
                status.buffer,
                param_context.eof,
                self.from_python,
            )

        else:
            raise UnsupportedSyntax()

    def context_exit(self, status: Syntax.Status) -> None:
        """Parser leaves a keyword context, for eg from 'rule:' to python code"""
        while self.target_indent > status.indent:
            callback_context: Context = self.context_stack.pop()
            if callback_context.syntax.accepts_python_code:
                self.flush_buffer()  # Flushes any code inside 'run' directive
            else:
                callback_context.syntax.check_empty()
            self.context = self.context_stack[-1]

        self.syntax.from_python = callback_context.syntax.from_python
        self.syntax.cur_indent = status.indent
        if self.target_indent > 0:
            self.syntax.target_indent = status.indent + 1
