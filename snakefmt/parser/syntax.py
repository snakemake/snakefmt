"""
Code in charge of parsing and validating Snakemake syntax
"""
import tokenize
from abc import ABC, abstractmethod
from re import match as re_match
from typing import NamedTuple, Optional

from snakefmt.exceptions import (
    ColonError,
    EmptyContextError,
    InvalidParameter,
    InvalidParameterSyntax,
    NewlineError,
    NoParametersError,
    NotAnIdentifierError,
    SyntaxFormError,
    TooManyParameters,
)
from snakefmt.types import (
    COMMENT_SPACING,
    TAB,
    Token,
    TokenIterator,
    col_nb,
    line_nb,
    not_empty,
)

# ___Token parsing___#
QUOTES = {'"', "'"}
BRACKETS_OPEN = {"(", "[", "{"}
BRACKETS_CLOSE = {")", "]", "}"}

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


def add_token_space(prev_token: Token, token: Token) -> bool:
    result = False
    if prev_token is not None and prev_token.type in spacing_triggers:
        if not operator_skip_spacing(prev_token, token):
            if token.type in spacing_triggers[prev_token.type]:
                result = True
    return result


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


class Parameter:
    """
    Holds the value of a parameter-accepting keyword
    """

    def __init__(self, token: Token):
        self.line_nb = line_nb(token)
        self.col_nb = col_nb(token)
        self.key = ""
        self.value = ""
        self.pre_comments, self.post_comments = list(), list()
        self.len = 0
        self.inline: bool = True
        self.fully_processed: bool = False
        self._has_inline_comment: bool = False

    def __repr__(self):
        if self.has_a_key():
            return f"{self.key}={self.value}"
        else:
            return self.value

    def is_empty(self) -> bool:
        return str(self) == ""

    def add_comment(self, comment: str, indent_level: int) -> None:
        if self.is_empty():
            self.pre_comments.append(comment)
        else:
            if self.inline:
                self._has_inline_comment = True
            self.post_comments.append(comment)

    def has_a_key(self) -> bool:
        return len(self.key) > 0

    def has_value(self) -> bool:
        return len(self.value) > 0

    def add_elem(self, prev_token: Token, token: Token):
        if add_token_space(prev_token, token) and len(self.value) > 0:
            self.value += " "

        if self.is_empty():
            self.col_nb = col_nb(token)

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


class Vocabulary:
    """
    Responsible for recognising snakemake keywords
    """

    spec = dict()

    def recognises(self, keyword: str) -> bool:
        return keyword in self.spec

    def get(self, keyword: str):
        return self.spec[keyword]


class Syntax(ABC):
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
        self.keyword_line = keyword_name
        assert target_indent >= 0
        self.target_indent = target_indent
        self.cur_indent = max(self.target_indent - 1, 0)
        self.code_indent = None
        self.comment = ""
        self.token = None

        if snakefile is not None:
            self.validate_keyword_line(snakefile)
            if self.token.type == tokenize.COMMENT:
                self.comment = f"{COMMENT_SPACING}{self.token.string}"
                self.token = next(snakefile)

    @abstractmethod
    def validate_keyword_line(self, snakefile: TokenIterator):
        """Checks the keyword-containing line is syntactically valid"""

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
        incident_syntax: "KeywordSyntax" = None,
        from_python: bool = False,
        accepts_py: bool = False,
    ):
        self.enter_context = True
        super().__init__(keyword_name, target_indent, snakefile)
        self.processed_keywords = set()
        self.accepts_python_code = accepts_py
        self.queriable = True
        self.from_python = from_python

        if incident_syntax is not None:
            if self.token.type != tokenize.NEWLINE:
                NewlineError(line_nb, self.keyword_line)
            if not from_python:
                incident_syntax.add_processed_keyword(self.token, self.keyword_line)

    def validate_keyword_line(self, snakefile: TokenIterator):
        self.token = next(snakefile)

        if self.keyword_name == "use":
            self.validate_userule_syntax(snakefile)
        else:
            self.validate_rulelike_syntax(snakefile)

    def validate_userule_syntax(self, snakefile: TokenIterator):
        identifier = r"[a-zA-Z_]\S*"
        use_syntax_regexp = (
            r"use rule (?:(?:{id})|\*)"
            r"(?: from {id})?(?: exclude {id}(?:\s*,\s*{id})*)?"
            r"(?: as {id})?( with[ ]?:)?$"
        ).format(id=identifier)
        use_ebnf_syntax = (
            '"use" "rule" (identifier | "*") '
            '"from" identifier '
            '["exclude" identifier {"," identifier}] '
            '["as" identifier] ["with" ":"]'
        )
        while not is_newline(self.token):
            if self.token.type == tokenize.COMMENT:
                break
            # Tokenizing splits up '<identifier>*' into two tokens
            if self.token.string not in ("*", ","):
                self.keyword_line += " "
            self.keyword_line += self.token.string
            try:
                self.token = next(snakefile)
            except StopIteration:
                break

        self.keyword_line = self.keyword_line.replace(
            "use rule*", "use rule *"
        ).replace("as*", "as *")
        match = re_match(use_syntax_regexp, self.keyword_line)
        if match is None:
            SyntaxFormError(self.line_nb, self.keyword_line, use_ebnf_syntax)
        if match.groups()[0] is None:
            self.enter_context = False
        else:
            # Gets added at formatting
            self.keyword_line = self.keyword_line.rstrip(": ")

    def validate_rulelike_syntax(self, snakefile: TokenIterator):
        if not is_colon(self.token):
            if self.token.type != tokenize.NAME:
                raise NotAnIdentifierError(
                    self.line_nb, self.token.string, self.keyword_line
                )
            self.keyword_line += f" {self.token.string}"
            self.token = next(snakefile)
        if not is_colon(self.token):
            ColonError(self.line_nb, self.token.string, self.keyword_line)
        self.token = next(snakefile)

    def add_processed_keyword(self, token: Token, keyword: str):
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

            if add_token_space(prev_token, token):
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

    def validate_keyword_line(self, snakefile: TokenIterator):
        self.token = next(snakefile)

        if not is_colon(self.token):
            ColonError(self.line_nb, self.token.string, self.keyword_line)
        self.token = next(snakefile)

    @property
    def all_params(self):
        return self.positional_params + self.keyword_params

    @property
    def in_brackets(self):
        return len(self._brackets) > 0

    def parse_params(self, snakefile: TokenIterator):
        cur_param = Parameter(self.token)
        prev_token = None

        while True:
            cur_param = self.process_token(cur_param, prev_token)
            try:
                prev_token = self.token
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

    def process_token(self, cur_param: Parameter, prev_token: Token) -> Parameter:
        token_type = self.token.type
        # Eager treatment of comments: tag them onto params
        if token_type == tokenize.COMMENT and not self.in_brackets:
            cur_param.add_comment(self.token.string, self.target_indent)
            return cur_param
        if is_newline(self.token):  # Special treatment for inline comments
            if not cur_param.is_empty():
                cur_param.inline = False
            if cur_param.has_value():
                cur_param.add_elem(prev_token, self.token)
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
        elif is_equal_sign(self.token) and not self.in_brackets and not self.in_lambda:
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
                if cur_param.value.lstrip() == "lambda":
                    self.in_lambda = True
            cur_param.add_elem(prev_token, self.token)
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


class ParamList(ParameterSyntax):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class InlineSingleParam(SingleParam):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class NoKeyParamList(ParamList):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if len(self.keyword_params) > 0:
            raise InvalidParameterSyntax(
                (
                    f"{self.line_nb}{self.keyword_name} definition does not accept "
                    f"key/value parameters"
                )
            )
