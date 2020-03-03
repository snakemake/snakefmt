from snakemake import parser as orig_parser
from black import format_str as black_format_str, FileMode
import tokenize
from typing import Tuple, Iterator
from collections import namedtuple

Token = namedtuple
TokenIterator = Iterator[Token]


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


class DuplicateKeyWordError(Exception):
    pass


class StopParsing(Exception):
    pass


class UnrecognisedKeyword(Exception):
    pass


class EmptyContextError(Exception):
    pass


class Context:
    keyword_name = ""
    indent = 0


class KeywordContext(Context):
    Status = namedtuple("Status", ["token", "indent", "buffer", "eof"])
    Processed_buffer = namedtuple(
        "Processed_buffer", ["token", "indent", "buffer", "eof"]
    )

    def __init__(self, name: str, indent: int):
        assert indent >= 0
        self.processed_keywords = set()
        self.name = name
        self.indent = indent

    def add_processed_keyword(self, token: Token):
        keyword = token.string
        if keyword in self.processed_keywords:
            raise DuplicateKeyWordError(
                f"{keyword} specified twice on line {token.start[0]}."
            )
        self.processed_keywords.add(keyword)

    def check_empty(self):
        if len(self.processed_keywords) == 0:
            raise EmptyContextError(
                f"Context '{self.name}' has no keywords attached to it."
            )

    def _get_next_queriable_token(self, snakefile: TokenIterator):
        buffer = ""
        indent = 0
        while True:
            cur_token = next(snakefile)
            if cur_token.type == tokenize.NAME:
                return self.Processed_buffer(cur_token, indent, buffer, False)
            elif cur_token.type == tokenize.ENCODING:
                continue
            elif cur_token.type == tokenize.ENDMARKER:
                return self.Processed_buffer(cur_token, indent, buffer, True)
            elif cur_token.type == tokenize.DEDENT:
                indent -= 0
            elif cur_token.type == tokenize.INDENT:
                indent += 1
            buffer += cur_token.string

    def get_next_keyword(self, snakefile: TokenIterator, target_indent: int = -1):
        assert target_indent >= -1
        if target_indent == -1:
            target_indent = self.indent
        buffer = ""

        while True:
            next_queriable = self._get_next_queriable_token(snakefile)
            buffer += next_queriable.buffer
            token = next_queriable.token

            if next_queriable.indent <= target_indent:
                return self.Status(
                    token, next_queriable.indent, buffer, next_queriable.eof
                )
            elif self.indent > 0:
                raise IndentationError(
                    f"In context of {self.name}, found overly indented keyword {token.string}."
                )
            buffer += token.string


class ParameterisedContext(Context):
    pass


class ParamSingle(ParameterisedContext):
    pass


class ParamList(ParameterisedContext):
    pass


class Language:
    spec = dict()

    def recognises(self, keyword: str) -> bool:
        if self.spec.get(keyword, None) is not None:
            return True
        return False

    def get(self, keyword: str) -> Tuple:
        return self.spec[keyword]


Grammar = namedtuple("Grammar", ["language", "context"])


class SnakeRule(Language):
    spec = dict(input=Grammar(None, ParamList), output=Grammar(None, ParamList))


class SnakeGlobal(Language):
    spec = dict(rule=Grammar(SnakeRule, KeywordContext))


class Parser:
    def __init__(self):
        self.indent = 0
        self.grammar = Grammar(SnakeGlobal(), KeywordContext("Global", self.indent))
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
            if status.eof:
                break
            if status.indent < self.indent:
                self.context_exit(status)

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
        if issubclass(KeywordContext, new_grammar.context):
            self.indent += 1
            self.grammar = Grammar(
                new_grammar.language, new_grammar.context(keyword, self.indent)
            )
            self.context_stack.append(self.grammar)
        elif issubclass(ParameterisedContext, new_grammar.context):
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
