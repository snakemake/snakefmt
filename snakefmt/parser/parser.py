import tokenize
from abc import ABC, abstractmethod

from snakefmt.exceptions import UnsupportedSyntax
from snakefmt.parser.grammar import Grammar, PythonCode, SnakeGlobal
from snakefmt.parser.syntax import KeywordSyntax, ParameterSyntax, Syntax, Vocabulary
from snakefmt.types import TokenIterator


class Snakefile:
    """
    Adapted from snakemake.parser.Snakefile
    """

    def __init__(self, fpath_or_stream, rulecount=0):
        try:
            self.stream = open(fpath_or_stream, encoding="utf-8")
        except TypeError:
            self.stream = fpath_or_stream

        self.tokens = tokenize.generate_tokens(self.stream.readline)
        self.rulecount = rulecount
        self.lines = 0

    def __next__(self):
        return next(self.tokens)


class Parser(ABC):
    def __init__(self, snakefile: TokenIterator):
        self.grammar = Grammar(
            SnakeGlobal(), KeywordSyntax("Global", target_indent=0, accepts_py=True)
        )
        self.context_stack = [self.grammar]
        self.snakefile: TokenIterator = snakefile
        self.from_python: bool = False

        status = self.context.get_next_queriable(self.snakefile)
        self.buffer = status.buffer

        while True:
            if status.indent < self.target_indent:
                self.context_exit(status)

            if status.eof:
                break

            self.from_python = False
            keyword = status.token.string
            if self.vocab.recognises(keyword):
                if status.indent > self.target_indent:
                    if self.context.from_python or status.pythonable:
                        self.from_python = True
                    else:  # Over-indented context gets reset
                        self.context.cur_indent = max(self.target_indent - 1, 0)
                self.flush_buffer(
                    from_python=self.from_python,
                    in_global_context=self.in_global_context,
                )
                status = self.process_keyword(status, self.from_python)
            else:
                if not self.context.accepts_python_code and not keyword[0] == "#":
                    raise SyntaxError(
                        f"L{status.token.start[0]}: Unrecognised keyword '{keyword}' "
                        f"in {self.context.keyword_name} definition"
                    )
                else:
                    self.buffer += keyword
                    status = self.context.get_next_queriable(self.snakefile)
                    self.buffer += status.buffer
            self.context.cur_indent = status.indent
        self.flush_buffer(
            from_python=self.from_python,
            final_flush=True,
            in_global_context=self.in_global_context,
        )

    @property
    def vocab(self) -> Vocabulary:
        return self.grammar.vocab

    @property
    def context(self) -> KeywordSyntax:
        return self.grammar.context

    @property
    def target_indent(self) -> int:
        return self.context.target_indent

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
        new_grammar = self.vocab.get(keyword)
        accepts_py = new_grammar.vocab is PythonCode
        if issubclass(new_grammar.context, KeywordSyntax):
            in_global_context = self.in_global_context
            self.grammar = Grammar(
                new_grammar.vocab(),
                new_grammar.context(
                    keyword,
                    self.context.cur_indent + 1,
                    snakefile=self.snakefile,
                    incident_context=self.context,
                    from_python=from_python,
                    accepts_py=accepts_py,
                ),
            )
            self.context_stack.append(self.grammar)
            self.process_keyword_context(in_global_context)

            status = self.context.get_next_queriable(self.snakefile)
            self.buffer += status.buffer
            return status

        elif issubclass(new_grammar.context, ParameterSyntax):
            param_context = new_grammar.context(
                keyword, self.context.cur_indent + 1, self.vocab, self.snakefile
            )
            self.process_keyword_param(param_context, self.in_global_context)
            self.context.add_processed_keyword(
                status.token, status.token.string, check_dup=False
            )
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
            callback_grammar: Grammar = self.context_stack.pop()
            if callback_grammar.context.accepts_python_code:
                self.flush_buffer()  # Flushes any code inside 'run' directive
            else:
                callback_grammar.context.check_empty()
            self.grammar = self.context_stack[-1]

        self.context.from_python = callback_grammar.context.from_python
        self.context.cur_indent = status.indent
        if self.target_indent > 0:
            self.context.target_indent = status.indent + 1
