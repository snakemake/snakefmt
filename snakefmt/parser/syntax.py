"""
Code in charge of parsing and validating Snakemake syntax
"""

import tokenize
from abc import ABC, abstractmethod
from re import match as re_match
from typing import Optional

from snakefmt import fstring_tokeniser_in_use
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
    Token,
    TokenIterator,
    col_nb,
    line_nb,
    not_empty,
)

# ___Token parsing___#
BRACKETS_OPEN = {"(", "[", "{"}
BRACKETS_CLOSE = {")", "]", "}"}

# ___Token spacing: for when cannot run black___#
spacing_triggers = {
    tokenize.NAME: {tokenize.NAME, tokenize.STRING, tokenize.NUMBER, tokenize.OP},
    tokenize.STRING: {tokenize.NAME, tokenize.OP},
    tokenize.NUMBER: {tokenize.NAME, tokenize.OP},
    tokenize.OP: {tokenize.NAME, tokenize.STRING, tokenize.NUMBER, tokenize.OP},
}

if fstring_tokeniser_in_use:
    spacing_triggers[tokenize.NAME].add(tokenize.FSTRING_START)
    spacing_triggers[tokenize.OP].add(tokenize.FSTRING_START)
    # A more compact spacing syntax than the above.
    fstring_spacing_triggers = {
        tokenize.NAME: {
            tokenize.NAME,
            tokenize.STRING,
            tokenize.NUMBER,
        },
        tokenize.STRING: {tokenize.NAME, tokenize.OP},
        tokenize.NUMBER: {tokenize.NAME},
        tokenize.OP: {
            tokenize.NAME,
            tokenize.STRING,
        },
    }


def split_code_string(string: str) -> list[str]:
    """Splits a code string into individual lines, preserving leading whitespace.
    >>> string = '''a = 1\nb = f\"\"\"\n{a}\n1\n2\n\"\"\"\nc=2'''
    >>> split_code_string(string)
    ['a = 1\nb = ', 'f\"\"\"\n{a}\n1\n2\n\"\"\"', '\nc=2']
    """
    lines = string.splitlines(keepends=True)
    lineiter = iter(lines)
    tokens = list(tokenize.generate_tokens(lambda: next(lineiter)))
    string_areas = []
    tokeniter = iter(tokens)
    for token in tokeniter:
        if token.type == tokenize.STRING:
            if token.start[0] != token.end[0]:
                string_areas.append((token.start, token.end))
        if fstring_tokeniser_in_use and token.type == tokenize.FSTRING_START:
            isin_fstring = 1
            for t1 in tokeniter:
                if t1.type == tokenize.FSTRING_START:
                    isin_fstring += 1
                elif t1.type == tokenize.FSTRING_END:
                    isin_fstring -= 1
                if isin_fstring == 0:
                    break
            if token.start[0] != t1.end[0]:
                string_areas.append((token.start, t1.end))
    code_str = [""]
    last_area = (1, 0), (1, 0)
    for area in string_areas:
        code_str[-1] += _extract_line_mid(lines, last_area[-1], area[0])
        code_str.append(_extract_line_mid(lines, area[0], area[1]))
        code_str.append("")
        last_area = area
    code_str[-1] += _extract_line_mid(
        lines, last_area[-1], (len(lines), len(lines[-1]))
    )
    return code_str


def _extract_line_mid(
    lines: list[str], start: tuple[int, int], end: tuple[int, int]
) -> str:
    s = "".join(lines[i] for i in range(start[0] - 1, end[0]))
    t = s[start[1] :]
    end_trim = end[1] - len(lines[end[0] - 1])
    if end_trim != 0:
        t = t[:end_trim]
    return t


def re_add_curly_bracket_if_needed(token: Token) -> str:
    result = ""
    if (
        fstring_tokeniser_in_use
        and token is not None
        and token.type == tokenize.FSTRING_MIDDLE
    ):
        if token.string.endswith("}"):
            result = "}"
        elif token.string.endswith("{"):
            result = "{"
    return result


def fstring_processing(
    token: Token, prev_token: Optional[Token], in_fstring: bool
) -> bool:
    """
    Returns True if we are entering, or have already entered and not exited,
    an f-string.
    """
    result = False
    if fstring_tokeniser_in_use:
        if prev_token is not None and prev_token.type == tokenize.FSTRING_START:
            result = True
        elif token.type != tokenize.FSTRING_END and in_fstring:
            result = True
    return result


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
    elif prev_token.type == tokenize.STRING and token.string == ",":
        return True
    else:
        return False


def add_token_space(
    prev_token: Optional[Token], token: Token, in_fstring: bool = False
) -> bool:
    result = False
    if prev_token is not None:
        if not operator_skip_spacing(prev_token, token):
            if not in_fstring:
                if token.type in spacing_triggers.get(prev_token.type, {}):
                    result = True
            elif token.type in fstring_spacing_triggers.get(prev_token.type, {}):
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

    def add_elem(self, prev_token: Token, token: Token, in_fstring: bool = False):
        if add_token_space(prev_token, token, in_fstring) and len(self.value) > 0:
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

    def __init__(
        self, keyword_name: str, keyword_indent: int, snakefile: TokenIterator = None
    ):
        self.keyword_name = keyword_name
        self.keyword_line = keyword_name
        assert keyword_indent >= 0
        self.keyword_indent = keyword_indent
        self.cur_indent = max(self.keyword_indent - 1, 0)
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
        keyword_indent: int,
        snakefile: TokenIterator = None,
        incident_syntax: "KeywordSyntax" = None,
        from_python: bool = False,
        accepts_py: bool = False,
    ):
        self.enter_context = True
        super().__init__(keyword_name, keyword_indent, snakefile)
        self.processed_keywords = set()
        self.accepts_python_code = accepts_py
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
                NotAnIdentifierError(self.line_nb, self.token.string, self.keyword_line)
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


class ParameterSyntax(Syntax):
    """Parses snakemake keywords that do not accept other keywords, eg 'input'"""

    def __init__(
        self,
        keyword_name: str,
        keyword_indent: int,
        incident_vocab: Vocabulary,
        snakefile: TokenIterator,
    ):
        super().__init__(keyword_name, keyword_indent, snakefile)
        self.positional_params, self.keyword_params = list(), list()
        self.eof = False
        self.incident_vocab = incident_vocab
        self._brackets = list()
        self.in_fstring = False
        self.in_lambda = False
        self.found_newline = False

        self.parse_params(snakefile)

    def validate_keyword_line(self, snakefile: TokenIterator):
        self.token = next(snakefile)

        if self.keyword_name == "storage":
            self.validate_named_keyword_line(snakefile)
        else:
            self.validate_anonymous_keyword_line(snakefile)

    def validate_named_keyword_line(self, snakefile: TokenIterator):
        if not is_colon(self.token):
            if self.token.type != tokenize.NAME:
                NotAnIdentifierError(self.line_nb, self.token.string, self.keyword_line)
            self.keyword_line += f" {self.token.string}"
            self.token = next(snakefile)
        if not is_colon(self.token):
            ColonError(self.line_nb, self.token.string, self.keyword_line)
        self.token = next(snakefile)

    def validate_anonymous_keyword_line(self, snakefile: TokenIterator):
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
            cur_param.value += re_add_curly_bracket_if_needed(self.token)
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
                exit = self.cur_indent < self.keyword_indent
            if exit:
                self.flush_param(cur_param, skip_empty=True)
        return exit

    def process_token(self, cur_param: Parameter, prev_token: Token) -> Parameter:
        token_type = self.token.type
        # f-string treatment (since python 3.12)
        self.in_fstring = fstring_processing(self.token, prev_token, self.in_fstring)
        if self.in_fstring:
            cur_param.add_elem(prev_token, self.token, self.in_fstring)
            return cur_param

        # Eager treatment of comments: tag them onto params
        if token_type == tokenize.COMMENT and not self.in_brackets:
            cur_param.add_comment(self.token.string, self.keyword_indent)
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
            self.cur_indent = max(self.cur_indent - 1, 0)
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
        if parameter.has_a_key() and not parameter.has_value():
            raise NoParametersError(
                f"{self.line_nb}In {self.keyword_name} definition, "
                f"keyword {parameter.key}"
            )

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
