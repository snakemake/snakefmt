"""
Code in charge of parsing and validating Snakemake syntax
"""
import tokenize
from typing import NamedTuple, Optional

from snakefmt.exceptions import (
    DuplicateKeyWordError,
    EmptyContextError,
    InvalidParameter,
    InvalidParameterSyntax,
    NamedKeywordError,
    NoParametersError,
    TooManyParameters,
)
from snakefmt.types import (
    COMMENT_SPACING,
    TAB,
    Parameter,
    Token,
    TokenIterator,
    col_nb,
    line_nb,
    not_empty,
)

possibly_named_keywords = {"rule", "checkpoint", "subworkflow"}

# ___Token parsing___#
QUOTES = {'"', "'"}
BRACKETS_OPEN = {"(", "[", "{"}
BRACKETS_CLOSE = {")", "]", "}"}


def is_colon(token: Token):
    return token.type == tokenize.OP and token.string == ":"


def is_newline(token: Token):
    return token.type == tokenize.NEWLINE or token.type == tokenize.NL


def brack_open(token: Token):
    return token.type == tokenize.OP and token.string in BRACKETS_OPEN


def brack_close(token: Token):
    return token.type == tokenize.OP and token.string in BRACKETS_CLOSE


def is_equal_sign(token: Token):
    return token.type == tokenize.OP and token.string == "="


def is_comma_sign(token: Token):
    return token.type == tokenize.OP and token.string == ","


# ___Token spacing: for when cannot run black___#
spacing_triggers = {
    tokenize.NAME: {tokenize.NAME, tokenize.STRING, tokenize.NUMBER, tokenize.OP},
    tokenize.STRING: {tokenize.NAME, tokenize.OP},
    tokenize.NUMBER: {tokenize.NAME, tokenize.OP},
    tokenize.OP: {tokenize.NAME, tokenize.STRING, tokenize.NUMBER, tokenize.OP},
}


def operator_skip_spacing(prev_token: Token, token: Token) -> bool:
    if prev_token.type != tokenize.OP and token.type != tokenize.OP:
        return False
    if (
        prev_token.string in BRACKETS_OPEN
        or prev_token.string == "."
        or token.string in BRACKETS_CLOSE
        or token.string in {"[", ":", "."}
    ):
        return True
    elif prev_token.type == tokenize.NAME and token.string == "(":
        return True
    else:
        return False


class Vocabulary:
    """
    Responsible for recognising snakemake keywords
    """

    spec = dict()

    def recognises(self, keyword: str) -> bool:
        return keyword in self.spec

    def get(self, keyword: str):
        return self.spec[keyword]


class Syntax:
    """
    Responsible for reading and processing tokens
    Classes derived from it raise syntax errors when snakemake syntax is not respected
    """

    class Status(NamedTuple):
        """Communicates the result of parsing a chunk of code"""

        token: Token
        indent: int
        buffer: str
        eof: bool
        pythonable: bool

    def __init__(
        self, keyword_name: str, target_indent: int, snakefile: TokenIterator = None
    ):
        self.keyword_name = keyword_name
        assert target_indent >= 0
        self.target_indent = target_indent
        self.cur_indent = max(self.target_indent - 1, 0)
        self.code_indent = None
        self.comment = ""
        self.token = None

        if snakefile is not None:
            self.parse_and_validate_keyword(snakefile)

    def parse_and_validate_keyword(self, snakefile: TokenIterator):
        self.token = next(snakefile)

        if not is_colon(self.token):
            if self.keyword_name in possibly_named_keywords:
                if self.token.type != tokenize.NAME:
                    raise NamedKeywordError(
                        (
                            f"{self.line_nb}Invalid name {self.token.string} "
                            f"for '{self.keyword_name}'"
                        )
                    )
                self.keyword_name += f" {self.token.string}"
                self.token = next(snakefile)
        if not is_colon(self.token):
            raise SyntaxError(
                (
                    f"{self.line_nb}Colon (not '{self.token.string}') expected after "
                    f"'{self.keyword_name}'"
                )
            )
        self.token = next(snakefile)

        if self.token.type == tokenize.COMMENT:
            self.comment = f"{COMMENT_SPACING}{self.token.string}"
            self.token = next(snakefile)

    @property
    def line_nb(self):
        return f"L{line_nb(self.token)}: "


class KeywordSyntax(Syntax):
    """Parses snakemake keywords that accept other keywords, eg 'rule'"""

    def __init__(
        self,
        keyword_name: str,
        target_indent: int,
        snakefile: TokenIterator = None,
        incident_context: "KeywordSyntax" = None,
        from_python: bool = False,
        accepts_py: bool = False,
    ):
        super().__init__(keyword_name, target_indent, snakefile)
        self.processed_keywords = set()
        self.accepts_python_code = accepts_py
        self.queriable = True
        self.from_python = from_python

        if incident_context is not None:
            if self.token.type != tokenize.NEWLINE:
                raise SyntaxError(
                    (
                        f"{self.line_nb}Newline expected after keyword "
                        f"'{self.keyword_name}'"
                    )
                )
            if not from_python:
                incident_context.add_processed_keyword(self.token, self.keyword_name)

    def add_processed_keyword(self, token: Token, keyword: str, check_dup: bool = True):
        if check_dup and keyword in self.processed_keywords:
            raise DuplicateKeyWordError(
                f"L{token.start[0]}: '{keyword}' specified twice."
            )
        self.processed_keywords.add(keyword)

    def check_empty(self):
        if len(self.processed_keywords) == 0:
            raise EmptyContextError(
                f"{self.line_nb}{self.keyword_name} has no keywords attached to it."
            )

    @property
    def effective_indent(self) -> int:
        return max(0, self.cur_indent - self.target_indent)

    def get_next_queriable(self, snakefile: TokenIterator) -> Syntax.Status:
        """Produces the next word that could be a snakemake keyword,
        and additional information in a :Syntax.Status:
        """
        buffer = ""
        newline = False
        pythonable = False
        prev_token: Optional[Token] = Token(tokenize.NAME)
        while True:
            token = next(snakefile)
            if token.type == tokenize.INDENT:
                self.cur_indent += 1
                prev_token = None
                continue
            elif token.type == tokenize.DEDENT:
                if self.cur_indent > 0:
                    self.cur_indent -= 1
                prev_token = None
                continue
            elif token.type == tokenize.ENDMARKER:
                return self.Status(token, self.cur_indent, buffer, True, pythonable)
            elif token.type == tokenize.COMMENT:
                if token.start[1] == 0:
                    return self.Status(token, 0, buffer, False, pythonable)
            elif is_newline(token):
                self.queriable, newline = True, True
                buffer += "\n"
                prev_token = None
                continue

            # Records relative tabbing, used for python code formatting
            if newline and not token.type == tokenize.COMMENT:
                buffer += TAB * self.effective_indent

            if token.type == tokenize.NAME and self.queriable:
                self.queriable = False
                return self.Status(token, self.cur_indent, buffer, False, pythonable)

            if prev_token is not None and prev_token.type in spacing_triggers:
                if not operator_skip_spacing(prev_token, token):
                    if token.type in spacing_triggers[prev_token.type]:
                        buffer += " "
            prev_token = token
            if newline:
                newline = False
            if not pythonable and token.type != tokenize.COMMENT:
                pythonable = True
            buffer += token.string


class ParameterSyntax(Syntax):
    """Parses snakemake keywords that do not accept other keywords, eg 'input'"""

    def __init__(
        self,
        keyword_name: str,
        target_indent: int,
        incident_vocab: Vocabulary,
        snakefile: TokenIterator,
    ):
        super().__init__(keyword_name, target_indent, snakefile)
        self.positional_params, self.keyword_params = list(), list()
        self.eof = False
        self.incident_vocab = incident_vocab
        self._brackets = list()
        self.in_lambda = False
        self.found_newline = False

        self.parse_params(snakefile)

    @property
    def all_params(self):
        return self.positional_params + self.keyword_params

    @property
    def in_brackets(self):
        return len(self._brackets) > 0

    def parse_params(self, snakefile: TokenIterator):
        cur_param = Parameter(self.token)

        while True:
            cur_param = self.process_token(cur_param)
            try:
                self.token = next(snakefile)
            except StopIteration:
                self.flush_param(cur_param, skip_empty=True)
                self.eof = True
                break
            if self.check_exit(cur_param):
                break

        if self.num_params() == 0:
            raise NoParametersError(f"{self.line_nb}In {self.keyword_name} definition.")

    def check_exit(self, cur_param: Parameter):
        exit = False
        if not self.found_newline:
            return exit
        if not_empty(self.token):
            # Special condition for comments: they appear before indents/dedents.
            if self.token.type == tokenize.COMMENT:
                if not cur_param.is_empty() and col_nb(self.token) < cur_param.col_nb:
                    exit = True
            else:
                exit = self.cur_indent < self.target_indent
            if exit:
                self.flush_param(cur_param, skip_empty=True)
        return exit

    def process_token(self, cur_param: Parameter) -> Parameter:
        token_type = self.token.type
        # Eager treatment of comments: tag them onto params
        if token_type == tokenize.COMMENT and not self.in_brackets:
            cur_param.add_comment(self.token.string, self.target_indent)
            return cur_param
        if is_newline(self.token):  # Special treatment for inline comments
            if not cur_param.is_empty():
                cur_param.inline = False
            if cur_param.has_value():
                cur_param.add_elem(self.token)
            self.found_newline = True
            return cur_param

        if cur_param.fully_processed:
            self.flush_param(cur_param)
            cur_param = Parameter(self.token)

        if token_type == tokenize.INDENT:
            self.cur_indent += 1
        elif token_type == tokenize.DEDENT:
            if self.cur_indent > 0:
                self.cur_indent -= 1
        elif is_equal_sign(self.token) and not self.in_brackets:
            cur_param.to_key_val_mode(self.token)
        elif is_comma_sign(self.token) and not self.in_brackets and not self.in_lambda:
            cur_param.fully_processed = True
        elif token_type != tokenize.ENDMARKER:
            if brack_open(self.token):
                self._brackets.append(self.token.string)
            if brack_close(self.token):
                self._brackets.pop()
            if is_colon(self.token) and self.in_lambda:
                self.in_lambda = False
            if len(cur_param.value.split()) == 1:
                if cur_param.value == "lambda":
                    self.in_lambda = True
                if self.incident_vocab.recognises(cur_param.value):
                    raise InvalidParameterSyntax(
                        (
                            f"{self.line_nb}Over-indented recognised keyword found: "
                            f"'{cur_param.value}'"
                        )
                    )
            cur_param.add_elem(self.token)
        return cur_param

    def flush_param(self, parameter: Parameter, skip_empty: bool = False) -> None:
        if not parameter.has_value() and skip_empty:
            return

        if parameter.has_a_key():
            self.keyword_params.append(parameter)
        else:
            self.positional_params.append(parameter)

    def num_params(self):
        return len(self.keyword_params) + len(self.positional_params)


# ___Parameter Syntax Validators___#
class SingleParam(ParameterSyntax):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.num_params() > 1:
            raise TooManyParameters(
                (
                    f"{self.line_nb}{self.keyword_name} definition expects a single "
                    f"parameter"
                )
            )
        if not len(self.keyword_params) == 0:
            raise InvalidParameter(
                (
                    f"{self.line_nb}{self.keyword_name} definition requires a "
                    f"positional (not key/value) parameter"
                )
            )


ParamList = ParameterSyntax


class RuleInlineSingleParam(SingleParam):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class NoKeywordParamList(ParameterSyntax):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if len(self.keyword_params) > 0:
            raise InvalidParameterSyntax(
                (
                    f"{self.line_nb}{self.keyword_name} definition does not accept "
                    f"key/value parameters"
                )
            )
