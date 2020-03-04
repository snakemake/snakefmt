import tokenize
from typing import Iterator
from collections import namedtuple

from ..exceptions import DuplicateKeyWordError, EmptyContextError

Token = namedtuple
TokenIterator = Iterator[Token]


class Syntax:
    keyword_name = ""
    indent = 0


class KeywordSyntax(Syntax):
    Status = namedtuple("Status", ["token", "indent", "buffer", "eof"])

    def __init__(self, keyword_name: str, indent: int, snakefile: TokenIterator = None):
        assert indent >= 0
        self.processed_keywords = set()
        self.keyword_name = keyword_name
        self.indent = indent
        self.line = ""

        if snakefile is not None:
            self.line = self.validate(snakefile)

    def validate(self, snakefile: TokenIterator):
        line = "\t" * (self.indent - 1) + self.keyword_name
        token = next(snakefile)
        if token.type == tokenize.NAME:
            line += f" {token.string}"
            token = next(snakefile)
        if token.string != ":":
            raise SyntaxError(f"L{token.start[0]}: Colon expected after '{line}'")
        line += token.string
        token = next(snakefile)
        if token.type == tokenize.COMMENT:
            line += f" {token.string}"
            token = next(snakefile)
        line += "\n"
        if token.type != tokenize.NEWLINE:
            raise SyntaxError(
                f"L{token.start[0]}: Newline expected after keyword {self.keyword_name}"
            )
        return line

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
                f"'{self.keyword_name}' has no keywords attached to it."
            )

    def _get_next_queriable_token(self, snakefile: TokenIterator):
        buffer = ""
        indent = max(self.indent - 1, 0)
        while True:
            cur_token = next(snakefile)
            if cur_token.type == tokenize.NAME:
                return self.Status(cur_token, indent, buffer, False)
            elif cur_token.type == tokenize.ENCODING:
                continue
            elif cur_token.type == tokenize.ENDMARKER:
                return self.Status(cur_token, indent, buffer, True)
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
                    f"In context of '{self.keyword_name}', found overly indented keyword '{token.string}'."
                )
            buffer += token.string


class ParameterSyntax(Syntax):
    pass


class ParamSingle(ParameterSyntax):
    pass


class ParamList(ParameterSyntax):
    pass
