import tokenize
from abc import ABC, abstractmethod

from snakefmt.exceptions import InvalidPython
from snakefmt.types import TokenIterator
from snakefmt.parser.grammar import Grammar, SnakeGlobal
from snakefmt.parser.syntax import (
    KeywordSyntax,
    ParameterSyntax,
    Parameter,
    accept_python_code,
)


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

    def __iter__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()


class Parser(ABC):
    def __init__(self, snakefile: TokenIterator):
        self.indent = 0
        self.grammar = Grammar(
            SnakeGlobal(), KeywordSyntax("Global", self.indent, accepts_py=True)
        )
        self.context_stack = [self.grammar]

        self.snakefile = snakefile
        self.result = ""
        self.buffer = ""
        self.first = True

        status = self.context.get_next_queriable(self.snakefile)
        self.buffer += status.buffer

        while True:
            if status.indent < self.indent:
                self.context_exit(status)

            if status.eof:
                break

            keyword = status.token.string
            if self.language.recognises(keyword):
                self.flush_buffer()
                new_status = self.process_keyword(status)
                if new_status is not None:
                    status = new_status
                    continue
            else:
                if not self.context.accepts_python_code:
                    raise SyntaxError(
                        f"L{status.token.start[0]}: Unrecognised keyword '{keyword}' "
                        f"in {self.context.keyword_name} definition"
                    )
                else:
                    self.buffer += keyword

            status = self.context.get_next_queriable(self.snakefile)
            self.buffer += status.buffer
        self.flush_buffer()

    @property
    def language(self):
        return self.grammar.language

    @property
    def context(self):
        return self.grammar.context

    @abstractmethod
    def flush_buffer(self):
        pass

    @abstractmethod
    def process_keyword_context(self):
        pass

    @abstractmethod
    def process_keyword_param(self, param_context):
        pass

    def process_keyword(self, status):
        keyword = status.token.string
        accepts_py = True if keyword in accept_python_code else False
        new_grammar = self.language.get(keyword)
        if self.indent == 0 and not self.first:
            self.result += "\n\n"
        if self.first:
            self.first = False
        if issubclass(new_grammar.context, KeywordSyntax):
            self.indent += 1
            self.grammar = Grammar(
                new_grammar.language(),
                new_grammar.context(
                    keyword, self.indent, self.context, self.snakefile, accepts_py
                ),
            )
            self.context_stack.append(self.grammar)
            self.process_keyword_context()
            return None

        elif issubclass(new_grammar.context, ParameterSyntax):
            param_context = new_grammar.context(
                keyword, self.indent + 1, self.language, self.snakefile
            )
            self.process_keyword_param(param_context)
            self.context.add_processed_keyword(status.token)
            return KeywordSyntax.Status(
                param_context.token,
                param_context.cur_indent,
                status.buffer,
                param_context.eof,
            )

    def context_exit(self, status):
        while self.indent > status.indent:
            callback_grammar = self.context_stack.pop()
            if callback_grammar.context.accepts_python_code:
                self.flush_buffer()
            else:
                callback_grammar.context.check_empty()
            self.indent -= 1
            self.grammar = self.context_stack[-1]
        assert len(self.context_stack) == self.indent + 1
