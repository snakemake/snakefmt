import tokenize
from black import format_str as black_format_str, FileMode
from typing import Iterator, List
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


def not_to_ignore(token):
    return (
        len(token.string) > 0
        and not token.string.isspace()
        and not token.type == tokenize.COMMENT
    )


class Syntax:
    def __init__(self, keyword_name: str, target_indent: int):
        self.keyword_name = keyword_name
        assert target_indent >= 0
        self.target_indent = target_indent
        self.cur_indent = max(self.target_indent - 1, 0)
        self.token = None

    @property
    def line_nb(self):
        return f"L{self.token.start[0]}: "


"""
Keyword parsing
"""


class KeywordSyntax(Syntax):
    Status = namedtuple("Status", ["token", "indent", "buffer", "eof"])

    def __init__(
        self,
        keyword_name: str,
        target_indent: int,
        snakefile: TokenIterator = None,
        accepts_py: bool = False,
    ):
        super().__init__(keyword_name, target_indent)
        self.processed_keywords = set()
        self.line = ""
        self.accepts_python_code = accepts_py

        if snakefile is not None:
            self.line = self.validate(snakefile)

    def validate(self, snakefile: TokenIterator):
        line = "\t" * (self.target_indent - 1) + self.keyword_name
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
            raise SyntaxError(
                f"{self.line_nb}Newline expected after '{self.keyword_name}'"
            )
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
        while True:
            cur_token = next(snakefile)
            if cur_token.type == tokenize.NAME:
                return self.Status(cur_token, self.cur_indent, buffer, False)
            elif cur_token.type == tokenize.ENCODING:
                continue
            elif cur_token.type == tokenize.ENDMARKER:
                return self.Status(cur_token, self.cur_indent, buffer, True)
            elif cur_token.type == tokenize.DEDENT:
                if self.cur_indent > 0:
                    self.cur_indent -= 1
            elif cur_token.type == tokenize.INDENT:
                self.cur_indent += 1
            buffer += cur_token.string

    def get_next_keyword(self, snakefile: TokenIterator):
        buffer = ""

        while True:
            next_queriable = self._get_next_queriable_token(snakefile)
            buffer += next_queriable.buffer
            self.token = next_queriable.token

            if next_queriable.indent <= self.target_indent:
                return self.Status(
                    self.token, self.cur_indent, buffer, next_queriable.eof
                )
            buffer += self.token.string


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

    def add_elem(self, token: Token):
        if token.type != tokenize.STRING:
            self.is_string = False

        self.value += token.string

    def to_key_val_mode(self, token: Token):
        if not self.has_value():
            raise InvalidParameterSyntax(
                f"L{token.start[0]}:Operator = used with no preceding key"
            )
        try:
            exec(f"{self.value} = 0")
        except SyntaxError:
            raise InvalidParameterSyntax(
                f"L{token.start[0]}:Invalid key {self.value}"
            ) from None
        self.key = self.value
        self.value = ""
        self.is_string = True


class ParameterSyntax(Syntax):
    def __init__(
        self, keyword_name: str, target_indent: int, snakefile: TokenIterator = None
    ):
        super().__init__(keyword_name, target_indent)
        self.processed_keywords = set()
        self.positional_params = list()
        self.keyword_params = list()
        self.eof = False

        self.token = next(snakefile)
        if not is_colon(self.token):
            raise SyntaxError(
                f"{self.line_nb}Colon expected after '{self.keyword_name}'"
            )

        self.parse_params(snakefile)

    @property
    def all_params(self):
        return self.positional_params + self.keyword_params

    def parse_params(self, snakefile: TokenIterator):
        found_newline = False
        cur_param = Parameter()

        while True:
            try:
                self.token = next(snakefile)
            except StopIteration:
                self.flush_param(cur_param, skip_empty=True)
                self.eof = True
                break
            t_t = self.token.type
            if found_newline and not_to_ignore(self.token):
                if self.cur_indent < self.target_indent:
                    self.flush_param(cur_param, skip_empty=True)
                    break
                elif t_t != tokenize.STRING:
                    raise IndentationError(
                        f"{self.line_nb}In context of '{self.keyword_name}', '{self.token.string}' is over-indented."
                    )
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
                cur_param.add_elem(self.token)

        if self.num_params() == 0:
            raise NoParametersError(f"{self.line_nb}In {self.keyword_name} definition.")

    def flush_param(self, parameter: Parameter, skip_empty: bool = False):
        if not parameter.has_value():
            if skip_empty:
                return
            else:
                raise NoParametersError(f"{self.line_nb}Empty parameter")

        if parameter.is_string:
            parameter.value = (
                parameter.value[0]
                + parameter.value[1:-1].replace('"', "")
                + parameter.value[-1]
            )
        parameter.value = black_format_str(parameter.value, mode=FileMode()).replace(
            "\n", ""
        )
        if parameter.has_key():
            self.keyword_params.append(parameter)
        else:
            self.positional_params.append(parameter)

    def num_params(self):
        return len(self.keyword_params) + len(self.positional_params)

    def check_param_type(self, param: Parameter, required_type):
        if required_type is str:
            failure = not param.is_string
        elif required_type is int:
            try:
                int(param.value)
            except ValueError:
                failure = True
        if failure:
            raise InvalidParameter(
                f"{self.line_nb}{self.keyword_name} definition requires parameter of type {required_type}"
            )


class SingleParam(ParameterSyntax):
    def __init__(
        self, keyword_name: str, target_indent: int, snakefile: TokenIterator = None
    ):
        super().__init__(keyword_name, target_indent, snakefile)

        if self.num_params() > 1:
            raise TooManyParameters(
                f"{self.line_nb}{self.keyword_name} definition expects a single parameter"
            )
        if not len(self.keyword_params) == 0:
            raise InvalidParameter(
                f"{self.line_nb}{self.keyword_name} definition requires a positional (not key/value) parameter"
            )


ParamList = ParameterSyntax


class StringParam(SingleParam):
    def __init__(
        self, keyword_name: str, target_indent: int, snakefile: TokenIterator = None
    ):
        super().__init__(keyword_name, target_indent, snakefile)

        self.check_param_type(self.positional_params[0], str)


class NumericParam(SingleParam):
    def __init__(
        self, keyword_name: str, target_indent: int, snakefile: TokenIterator = None
    ):
        super().__init__(keyword_name, target_indent, snakefile)

        self.check_param_type(self.positional_params[0], int)


class StringNoKeywordParamList(ParameterSyntax):
    def __init__(
        self, keyword_name: str, target_indent: int, snakefile: TokenIterator = None
    ):
        super().__init__(keyword_name, target_indent, snakefile)

        if len(self.keyword_params) > 0:
            raise InvalidParameterSyntax(
                f"{self.line_nb}{self.keyword_name} definition does not accept key/value parameters"
            )
        for param in self.all_params:
            self.check_param_type(param, str)
