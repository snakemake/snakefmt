import textwrap
import tokenize
from black import format_str as black_format_str, FileMode
from typing import Iterator, List
from collections import namedtuple

DEFAULT_LINE_LENGTH = 88


def run_black_format_str(input: str, indent: int) -> str:
    fmted = black_format_str(input, mode=FileMode())[:-1]
    indented = textwrap.indent(fmted, "\t" * indent)
    return indented


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


def brack_open(token):
    return token.type == tokenize.OP and token.string == "("


def brack_close(token):
    return token.type == tokenize.OP and token.string == ")"


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
        self.queriable = True

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

    def get_next_queriable(self, snakefile):
        buffer = ""
        newline = False
        while True:
            token = next(snakefile)
            t_t = token.type
            if t_t == tokenize.NAME:
                if newline:
                    buffer += "\t" * self.cur_indent
                    newline = False
                if self.cur_indent <= self.target_indent:
                    if self.queriable:
                        self.queriable = False
                        return self.Status(token, self.cur_indent, buffer, False)
                buffer += " "
            elif t_t == tokenize.INDENT:
                self.cur_indent += 1
                continue
            elif t_t == tokenize.DEDENT:
                if self.cur_indent > 0:
                    self.cur_indent -= 1
            elif t_t == tokenize.ENDMARKER:
                return self.Status(token, self.cur_indent, buffer, True)
            elif t_t == tokenize.NEWLINE:
                self.queriable, newline = True, True
            buffer += token.string


"""
Parameter parsing
"""


class Parameter:
    def __init__(self):
        self.key = ""
        self.value = ""
        self.formatted_string_value = ""
        self.comments = list()
        self.is_string = True
        self.len = 0

    def has_key(self) -> bool:
        return len(self.key) > 0

    def has_value(self) -> bool:
        return len(self.value) > 0 or len(self.formatted_string_value) > 0

    def add_elem(self, token: Token):
        if token.type != tokenize.STRING:
            self.is_string = False
        if len(self.value) > 0 and token.type == tokenize.NAME:
            self.value += " "

        self.value += token.string
        self.len += len(token.string)

        if self.is_string:
            self.value = '"' + eval(self.value) + '"'
            if self.len > DEFAULT_LINE_LENGTH:
                self.formatted_string_value += self.value + "\n"
                self.value = ""
                self.len = 0

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
        self.found_newline, self.in_brackets = False, False
        cur_param = Parameter()

        while True:
            try:
                self.token = next(snakefile)
            except StopIteration:
                self.flush_param(cur_param, skip_empty=True)
                self.eof = True
                break
            if self.check_exit(cur_param):
                break
            cur_param = self.process_token(cur_param)

        if self.num_params() == 0:
            raise NoParametersError(f"{self.line_nb}In {self.keyword_name} definition.")

    def check_exit(self, cur_param: Parameter):
        if self.found_newline and not_to_ignore(self.token):
            if self.cur_indent < self.target_indent:
                self.flush_param(cur_param, skip_empty=True)
                return True
            elif (
                self.token.type != tokenize.STRING
                and self.cur_indent > self.target_indent
            ):
                raise IndentationError(
                    f"{self.line_nb}In context of '{self.keyword_name}', '{self.token.string}' is over-indented."
                )
        return False

    def process_token(self, cur_param: Parameter):
        t_t = self.token.type
        if t_t == tokenize.INDENT:
            self.cur_indent += 1
        elif t_t == tokenize.DEDENT:
            self.cur_indent -= 1
        elif t_t == tokenize.NEWLINE or t_t == tokenize.NL:
            self.found_newline = True
        elif t_t == tokenize.COMMENT:
            cur_param.comments.append(self.token.string)
        elif is_equal_sign(self.token) and not self.in_brackets:
            cur_param.to_key_val_mode(self.token)
        elif is_comma_sign(self.token) and not self.in_brackets:
            self.flush_param(cur_param)
            cur_param = Parameter()
        elif is_colon(self.token):
            raise InvalidParameterSyntax(
                f"{self.line_nb}Keyword-like syntax found: '{cur_param.value}:' \n"
                f"Is your indentation correct?"
            )
        elif t_t != tokenize.ENDMARKER:
            if brack_open(self.token):
                self.in_brackets = True
            if brack_close(self.token):
                self.in_brackets = False
            cur_param.add_elem(self.token)
        return cur_param

    def flush_param(self, parameter: Parameter, skip_empty: bool = False):
        if not parameter.has_value():
            if skip_empty:
                return
            else:
                raise NoParametersError(f"{self.line_nb}Empty parameter")

        parameter.value = run_black_format_str(parameter.value, 0)
        if parameter.is_string:
            parameter.value = parameter.formatted_string_value + parameter.value
        used_indent = "\t" * self.target_indent
        parameter.value = parameter.value.replace("\n", f"\n{used_indent}")
        if parameter.has_key():
            self.keyword_params.append(parameter)
        else:
            self.positional_params.append(parameter)

    def num_params(self):
        return len(self.keyword_params) + len(self.positional_params)

    def check_param_type(self, param: Parameter, required_type):
        failure = False
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


class NoKeywordParamList(ParameterSyntax):
    def __init__(
        self, keyword_name: str, target_indent: int, snakefile: TokenIterator = None
    ):
        super().__init__(keyword_name, target_indent, snakefile)

        if len(self.keyword_params) > 0:
            raise InvalidParameterSyntax(
                f"{self.line_nb}{self.keyword_name} definition does not accept key/value parameters"
            )
