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


def not_space(token):
    return len(token.string) > 0 and not token.string.isspace()


class Syntax:
    def __init__(self, keyword_name: str, indent: int):
        self.keyword_name = keyword_name
        assert indent >= 0
        self.indent = indent
        self.token = None

    @property
    def line_nb(self):
        return f"L{self.token.start[0]}: "


"""
Keyword parsing
"""


class KeywordSyntax(Syntax):
    Status = namedtuple("Status", ["token", "indent", "buffer", "eof"])

    def __init__(self, keyword_name: str, indent: int, snakefile: TokenIterator = None):
        super().__init__(keyword_name, indent)
        self.processed_keywords = set()
        self.line = ""

        if snakefile is not None:
            self.line = self.validate(snakefile)

    def validate(self, snakefile: TokenIterator):
        line = "\t" * (self.indent - 1) + self.keyword_name
        self.token = next(snakefile)
        if self.token.type == tokenize.NAME:
            line += f" {self.token.string}"
            self.token = next(snakefile)
        if not is_colon(self.token):
            raise SyntaxError(f"{self.line_nb}Colon expected after '{line}'")
        line += self.token.string
        token = next(snakefile)
        if token.type == tokenize.COMMENT:
            line += f" {token.string}"
            token = next(snakefile)
        line += "\n"
        if token.type != tokenize.NEWLINE:
            raise SyntaxError(f"{self.line_nb}Newline expected after '{line}'")
        return line

    def add_processed_keyword(self, token: Token):
        keyword = token.string
        if keyword in self.processed_keywords:
            raise DuplicateKeyWordError(f"{self.line_nb}{keyword} specified twice.")
        self.processed_keywords.add(keyword)

    def check_empty(self):
        if len(self.processed_keywords) == 0:
            raise EmptyContextError(
                f"{self.line_nb}{self.keyword_name} has no keywords attached to it."
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
                    f"{self.line_nb}In context of '{self.keyword_name}', found overly indented keyword '{token.string}'."
                )
            buffer += token.string


"""
Parameter parsing
"""


class Parameter:
    def __init__(self):
        self.key = ""
        self.value = ""
        self.comments = list()
        self.is_string = True

    def has_key(self) -> bool:
        return len(self.key) > 0

    def has_value(self) -> bool:
        return len(self.value) > 0

    def add_elem(self, prev_token: Token, token: Token):
        if token.type != tokenize.STRING:
            self.is_string = False

        if (
            (prev_token.type == tokenize.STRING and token.type == tokenize.NAME)
            or (prev_token.type == tokenize.NAME and token.type == tokenize.STRING)
            or (prev_token.type == tokenize.NAME and token.type == tokenize.NAME)
        ):
            self.value += " "
        self.value += token.string

    def to_key_val_mode(self, token: Token):
        if not self.has_value():
            raise InvalidParameterSyntax(
                f"{self.line_nb}Operator = used with no preceding key"
            )
        if self.is_string:
            raise InvalidParameter(
                f"{self.line_nb}Key {self.value} should not be a string"
            )
        self.key = self.value
        self.value = ""
        self.is_string = True


class ParameterSyntax(Syntax):
    def __init__(self, keyword_name: str, indent: int, snakefile: TokenIterator = None):
        super().__init__(keyword_name, indent)
        self.processed_keywords = set()
        self.positional_params = list()
        self.keyword_params = list()
        self.eof = False

        found_newline = False
        self.cur_indent = self.indent
        cur_param = Parameter()

        self.token = next(snakefile)
        if not is_colon(self.token):
            raise SyntaxError(
                f"{self.line_nb}Colon expected after '{self.keyword_name}'"
            )

        while True:
            try:
                prev_token = self.token
                self.token = next(snakefile)
            except StopIteration:
                self.flush_param(cur_param, skip_empty=True)
                self.eof = True
                break
            t_t = self.token.type
            if (
                found_newline
                and self.cur_indent <= self.indent
                and not_space(self.token)
            ):
                self.flush_param(cur_param, skip_empty=True)
                self.token = self.token
                break
            if t_t == tokenize.INDENT:
                self.cur_indent += 1
            elif t_t == tokenize.DEDENT:
                self.cur_indent -= 1
            elif t_t == tokenize.NEWLINE or t_t == tokenize.NL:
                found_newline = True
            elif t_t == tokenize.COMMENT:
                cur_param.comments.append(self.token.string)
            elif is_equal_sign(self.token):
                cur_param.to_key_val_mode(self.token)
            elif is_comma_sign(self.token):
                self.flush_param(cur_param)
                cur_param = Parameter()
            else:
                cur_param.add_elem(prev_token, self.token)

        if self.num_params() == 0:
            raise NoParametersError(f"{self.line_nb}In {self.keyword_name} definition.")

    def flush_param(self, parameter: Parameter, skip_empty: bool = False):
        if not parameter.has_value():
            if skip_empty:
                return
            else:
                raise InvalidParameterSyntax(f"{self.line_nb}Empty parameter")
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
            raise TooManyParameters(
                f"{self.line_nb}{self.keyword_name} expects a single parameter"
            )
        if not len(self.keyword_params) == 0:
            raise InvalidParameter(
                f"{self.line_nb}{self.keyword_name} definition requires a single positional parameter"
            )


class StringParamSingle(ParamSingle):
    def __init__(self, keyword_name: str, indent: int, snakefile: TokenIterator = None):
        super().__init__(keyword_name, indent, snakefile)

        if not self.positional_params[0].is_string:
            raise InvalidParameter(
                f"{self.line_nb}{self.keyword_name} definition requires a single string parameter"
            )


class NumericParamSingle(ParamSingle):
    def __init__(self, keyword_name: str, indent: int, snakefile: TokenIterator = None):
        super().__init__(keyword_name, indent, snakefile)

        try:
            ev = eval(self.positional_params[0].value)
            if type(ev) is not int:
                raise InvalidParameter(
                    f"{self.line_nb}{self.keyword_name} definition requires a single numeric parameter"
                )
        except Exception as e:
            print(f"In keyword {self.keyword_name}: ")
            raise


class ParamList(ParameterSyntax):
    def __init__(self, keyword_name: str, indent: int, snakefile: TokenIterator = None):
        super().__init__(keyword_name, indent, snakefile)
