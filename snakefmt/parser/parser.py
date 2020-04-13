import tokenize
from abc import ABC, abstractmethod

from snakefmt.types import TokenIterator
from snakefmt.parser.grammar import Grammar, SnakeGlobal, PythonCode
from snakefmt.exceptions import UnsupportedSyntax
from snakefmt.parser.syntax import (
    Vocabulary,
    Syntax,
    KeywordSyntax,
    ParameterSyntax,
    possibly_duplicated_keywords,
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
            if self.vocab.recognises(keyword):
                from_python = False
                if status.indent > self.target_indent:
                    if self.context.from_python or status.pythonable:
                        from_python = True
                    else:  # Over-indented context gets reset
                        self.context.cur_indent = max(self.target_indent - 1, 0)
                self.flush_buffer(from_python)
                status = self.process_keyword(status, from_python)
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
        self.flush_buffer()

    @property
    def vocab(self) -> Vocabulary:
        return self.grammar.vocab

    @property
    def context(self) -> KeywordSyntax:
        return self.grammar.context

    @property
    def target_indent(self) -> int:
        return self.context.target_indent

    @abstractmethod
    def flush_buffer(self, from_python: bool = False) -> None:
        pass

    @abstractmethod
    def process_keyword_context(self):
        pass

    @abstractmethod
    def process_keyword_param(self, param_context):
        pass

    def process_keyword(
        self, status: Syntax.Status, from_python: bool = False
    ) -> Syntax.Status:
        keyword = status.token.string
        new_grammar = self.vocab.get(keyword)
        accepts_py = new_grammar.vocab is PythonCode
        if issubclass(new_grammar.context, KeywordSyntax):
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
            self.process_keyword_context()

            status = self.context.get_next_queriable(self.snakefile)
            self.buffer += status.buffer
            return status

        elif issubclass(new_grammar.context, ParameterSyntax):
            param_context = new_grammar.context(
                keyword, self.context.cur_indent + 1, self.vocab, self.snakefile
            )
            self.process_keyword_param(param_context)
            if keyword not in possibly_duplicated_keywords and not from_python:
                self.context.add_processed_keyword(status.token, status.token.string)
            return Syntax.Status(
                param_context.token,
                param_context.cur_indent,
                status.buffer,
                param_context.eof,
                False,
            )

        else:
            raise UnsupportedSyntax()

    def context_exit(self, status: Syntax.Status) -> None:
        while self.target_indent > status.indent:
            callback_grammar: Grammar = self.context_stack.pop()
            if callback_grammar.context.accepts_python_code:
                self.flush_buffer()
            else:
                callback_grammar.context.check_empty()
            self.grammar = self.context_stack[-1]

        self.context.from_python = callback_grammar.context.from_python
        self.context.cur_indent = status.indent
        if self.target_indent > 0:
            self.target_indent = status.indent + 1
