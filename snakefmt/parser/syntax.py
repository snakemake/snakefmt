import tokenize
from typing import Iterator
from collections import namedtuple

from ..exceptions import (
    DuplicateKeyWordError,
    EmptyContextError,
    NoParametersError,
    InvalidParameterSyntax,
    TooManyParameters,
    InvalidParameter,
)

Token = namedtuple
TokenIterator = Iterator[Token]


def is_colon(token):
    return token.type == tokenize.OP and token.string == ":"


def is_equal_sign(token):
    return token.type == tokenize.OP and token.string == "="


def is_comma_sign(token):
    return token.type == tokenize.OP and token.string == ","


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
        if not is_colon(token):
            raise SyntaxError(f"L{token.start[0]}: Colon expected after '{line}'")
        line += token.string
        token = next(snakefile)
        if token.type == tokenize.COMMENT:
            line += f" {token.string}"
            token = next(snakefile)
        line += "\n"
        if token.type != tokenize.NEWLINE:
            raise SyntaxError(f"L{token.start[0]}: Newline expected after '{line}'")
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


class Parameter:
    def __init__(self):
        self.key = ""
        self.value = ""
        self.comment = list()
        self.is_string = True

    def has_key(self) -> bool:
        return len(self.key) > 0

    def has_value(self) -> bool:
        return len(self.value) > 0

    def add_elem(self, token: Token):
        if token.type != tokenize.STRING:
            if self.is_string and len(self.value) > 0:
                raise InvalidParameterSyntax(f"L{token.start[0]}: {self.value}")
            self.is_string = False
        else:
            if not self.is_string:
                raise InvalidParameterSyntax(f"L{token.start[0]}: {self.value}")

        self.value += token.string

    def to_key_val_mode(self):
        if not self.has_value():
            raise InvalidParameterSyntax("Operator = used with no preceding key")
        self.key = self.value
        self.value = ""
        self.is_string = True


class ParameterSyntax(Syntax):
    def __init__(self, keyword_name: str, indent: int, snakefile: TokenIterator = None):
        assert indent >= 0
        self.processed_keywords = set()
        self.keyword_name = keyword_name
        self.indent = indent
        self.positional_params = list()
        self.keyword_params = list()

        found_newline = False
        cur_indent = self.indent
        cur_param = Parameter()

        token = next(snakefile)
        if not is_colon(token):
            raise SyntaxError(
                f"L{token.start[0]}: Colon expected after '{self.keyword_name}'"
            )

        while True:
            if found_newline and cur_indent <= self.indent and t_t != tokenize.NEWLINE:
                self.flush_param(cur_param, token)
                break
            token = next(snakefile)
            t_t = token.type
            if t_t == tokenize.INDENT:
                cur_indent += 1
            elif t_t == tokenize.DEDENT:
                cur_indent -= 1
            elif t_t == tokenize.NEWLINE:
                found_newline = True
            elif t_t == tokenize.COMMENT:
                cur_param.comment.append(token.string)
            elif is_equal_sign(token):
                cur_param.to_key_val_mode()
            elif is_comma_sign(token):
                self.flush_param(cur_param, token)
                cur_param = Parameter()
            else:
                cur_param.add_elem(token)

        if self.num_params() == 0:
            raise NoParametersError(f"In {self.keyword_name} definition.")

    def flush_param(self, parameter: Parameter, token: Token):
        if not parameter.has_value():
            raise InvalidParameterSyntax(f"L{token.start[0]}: Empty parameter")
        if parameter.has_key():
            self.keyword_params.append(parameter)
        else:
            self.positional_params.append(parameter)

    def num_params(self):
        return len(self.keyword_params) + len(self.positional_params)


class ParamSingle(ParameterSyntax):
    def __init__(self, keyword_name: str, indent: int, snakefile: TokenIterator = None):
        super().__init__(keyword_name, indent, snakefile)

        if self.num_params() > 1:
            raise TooManyParameters(f"{self.keyword_name} expects a single parameter")
        if not len(self.keyword_params) == 0:
            raise InvalidParameter(
                f"{self.keyword_name} definition requires "
                f"have a single positional parameter"
            )


class StringParamSingle(ParamSingle):
    def __init__(self, keyword_name: str, indent: int, snakefile: TokenIterator = None):
        super().__init__(keyword_name, indent, snakefile)

        if not self.keyword_params[0].is_string:
            raise InvalidParameter(
                f"{self.keyword_name} definition requires " f"a single string parameter"
            )


class ParamList(ParameterSyntax):
    def __init__(self, keyword_name: str, indent: int, snakefile: TokenIterator = None):
        super().__init__(keyword_name, indent, snakefile)
