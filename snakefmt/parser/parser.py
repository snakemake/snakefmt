import tokenize
from abc import ABC, abstractmethod

from snakefmt.types import TokenIterator
from snakefmt.parser.grammar import Grammar, SnakeGlobal
from snakefmt.parser.syntax import (
    Syntax,
    KeywordSyntax,
    ParameterSyntax,
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
        self.grammar = Grammar(
            SnakeGlobal(), KeywordSyntax("Global", target_indent=0, accepts_py=True)
        )
        self.context_stack = [self.grammar]
        self.snakefile = snakefile

        status = self.context.get_next_queriable(self.snakefile)
        self.buffer = status.buffer

        while True:
            if status.indent < self.target_indent:
                self.context_exit(status)

            if status.eof:
                break

            keyword = status.token.string
            if self.language.recognises(keyword):
                self.flush_buffer(status)
                status = self.process_keyword(status)
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

    @property
    def target_indent(self) -> int:
        return self.context.target_indent

    @abstractmethod
    def flush_buffer(self, status: Syntax.Status = None) -> None:
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
        if issubclass(new_grammar.context, KeywordSyntax):
            new_target_indent = self.context.cur_indent + 1
            self.grammar = Grammar(
                new_grammar.language(),
                new_grammar.context(
                    keyword,
                    new_target_indent,
                    self.context,
                    self.snakefile,
                    accepts_py,
                ),
            )
            self.context_stack.append(self.grammar)
            self.process_keyword_context()

            status = self.context.get_next_queriable(self.snakefile)
            self.buffer += status.buffer
            return status

        elif issubclass(new_grammar.context, ParameterSyntax):
            param_context = new_grammar.context(
                keyword, self.target_indent + 1, self.language, self.snakefile
            )
            self.process_keyword_param(param_context)
            self.context.add_processed_keyword(status.token)
            return Syntax.Status(
                param_context.token,
                param_context.cur_indent,
                status.buffer,
                param_context.eof,
            )

    def context_exit(self, status: Syntax.Status) -> None:
        while self.target_indent > status.indent:
            callback_grammar = self.context_stack.pop()
            if callback_grammar.context.accepts_python_code:
                self.flush_buffer()
            else:
                callback_grammar.context.check_empty()
            self.grammar = self.context_stack[-1]
            self.context.cur_indent = max(self.target_indent - 1, 0)
