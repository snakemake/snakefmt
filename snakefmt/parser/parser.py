from snakemake import parser as orig_parser
from black import format_str as black_format_str, FileMode
import tokenize

from .grammar import Grammar, SnakeGlobal
from .syntax import TokenIterator, KeywordSyntax, ParameterSyntax
from ..exceptions import UnrecognisedKeyword


def getUntil(snakefile: TokenIterator, type) -> str:
    result = ""
    while True:
        token = next(snakefile)
        if token.type == tokenize.NAME:
            result += " "
        result += token.string
        if token.type == type or token.type == tokenize.ENDMARKER:
            break
    return result


class Parser:
    def __init__(self):
        self.indent = 0
        self.grammar = Grammar(SnakeGlobal(), KeywordSyntax("Global", self.indent))
        self.context_stack = [self.grammar]

    @property
    def language(self):
        return self.grammar.language

    @property
    def context(self):
        return self.grammar.context


class Formatter(Parser):
    def __init__(self, snakefile_path: str):
        super().__init__()
        self.snakefile = orig_parser.Snakefile(snakefile_path)
        self.formatted = ""
        self.buffer = ""

        status = self.context.get_next_keyword(self.snakefile)
        self.buffer += status.buffer

        while True:
            if status.indent < self.indent:
                self.context_exit(status)

            if status.eof:
                break

            keyword = status.token.string
            if self.language.recognises(keyword):
                self.flush_and_format_buffer()
                self.process_keyword(status)
            else:
                if self.indent != 0:
                    raise UnrecognisedKeyword(f"{keyword}")
                else:
                    self.buffer += keyword
                    self.buffer += getUntil(self.snakefile, tokenize.NEWLINE)

            status = self.context.get_next_keyword(self.snakefile)
            self.buffer += status.buffer
        self.flush_and_format_buffer()

    def get_formatted(self):
        return self.formatted

    def process_keyword(self, status):
        keyword = status.token.string
        new_grammar = self.language.get(keyword)
        if issubclass(KeywordSyntax, new_grammar.context):
            self.indent += 1
            self.grammar = Grammar(
                new_grammar.language(),
                new_grammar.context(keyword, self.indent, self.snakefile),
            )
            self.context_stack.append(self.grammar)
            self.formatted += self.grammar.context.line
        elif issubclass(ParameterSyntax, new_grammar.context):
            self.context.add_processed_keyword(status.token)

    def context_exit(self, status):
        while self.indent > status.indent:
            callback_grammar = self.context_stack.pop()
            callback_grammar.context.check_empty()
            self.indent -= 1
            self.grammar = self.context_stack[-1]
        assert len(self.context_stack) == self.indent + 1

    def flush_and_format_buffer(self):
        if len(self.buffer) > 0:
            self.formatted += black_format_str(self.buffer, mode=FileMode())
            self.buffer = ""
