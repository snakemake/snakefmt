import tokenize
from typing import Iterator, NamedTuple, Tuple

from snakefmt.exceptions import InvalidParameterSyntax

TAB = "    "  # PEP8, indentation will be coded as 4 spaces
COMMENT_SPACING = "  "  # PEP8, minimum of two spaces for inline comments


class Token(NamedTuple):
    type: int
    string: str = ""
    start: Tuple[int, int] = (-1, -1)
    end: Tuple[int, int] = (-1, -1)


def line_nb(token: Token) -> int:
    return token.start[0]


def col_nb(token: Token) -> int:
    return token.start[1]


def not_empty(token: Token):
    return len(token.string) > 0 and not token.string.isspace()


TokenIterator = Iterator[Token]


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

    def add_elem(self, token: Token):
        if token.type == tokenize.NAME and len(self.value) > 0:
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
