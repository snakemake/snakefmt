from snakemake import parser as orig_parser
import tokenize
from typing import Tuple, Iterator
from collections import namedtuple

Token = namedtuple
TokenIterator = Iterator[Token]


class DuplicateKeyWordError(Exception):
    pass


class StopParsing(Exception):
    pass


class Context:
    keyword_name = ""
    indent = 0


class KeywordContext(Context):
    Status = namedtuple("Status", ["token", "indent", "buffer"])

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

    def get_next_queriable_token(self, snakefile: TokenIterator):
        Processed_buffer = namedtuple("Processed_buffer", ["token", "indent", "buffer"])
        buffer = ""
        indent = 0
        while True:
            cur_token = next(snakefile)
            if cur_token.type == tokenize.NAME:
                return Processed_buffer(cur_token, indent, buffer)
            elif cur_token.type == tokenize.ENCODING:
                continue
            elif cur_token.type == tokenize.ENDMARKER:
                raise StopParsing()
            elif cur_token.type == tokenize.NEWLINE:
                indent = 0
            elif cur_token.type == tokenize.INDENT:
                indent += 1
            buffer += cur_token.string

    def get_next_keyword(self, snakefile: TokenIterator, target_indent: int = -1):
        assert target_indent >= -1
        if target_indent == -1:
            target_indent = self.indent

        while True:
            next_queriable = self.get_next_queriable_token(snakefile)
            token = next_queriable.token

            if next_queriable.indent <= target_indent:
                return self.Status(token, next_queriable.indent, next_queriable.buffer)
            elif self.indent > 0:
                raise IndentationError(
                    f"In context of {self.name}, found overly indented keyword {token.string}."
                )


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


Grammar = namedtuple("TiedContext", ["language", "context"])


class SnakeRule(Language):
    spec = dict(input=Grammar(None, ParamList), output=Grammar(None, ParamList))


class SnakeGlobal(Language):
    spec = dict(rule=Grammar(SnakeRule, KeywordContext))


class Parser:
    grammar = Grammar(SnakeGlobal, KeywordContext)

    @property
    def language(self):
        return self.grammar.language

    @property
    def context(self):
        return self.grammar.context


class Formatter(Parser):
    def __init__(self, snakefile_path: str):
        self.snakefile = orig_parser.Snakefile(snakefile_path)
        self.formatted = ""
