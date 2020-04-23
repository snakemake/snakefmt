import tokenize
from typing import Iterator, NamedTuple, Tuple

from snakefmt.exceptions import InvalidParameterSyntax


class Token(NamedTuple):
    type: int
    string: str = ""
    start: Tuple[int, int] = (-1, -1)
    end: Tuple[int, int] = (-1, -1)


TokenIterator = Iterator[Token]


class Parameter:
    """
    Holds the value of a parameter-accepting keyword
    """

    def __init__(self, line_nb: str):
        self.line_nb = line_nb
        self.key = ""
        self.value = ""
        self.comments = list()
        self.len = 0

    def __repr__(self):
        if self.has_a_key():
            return f"{self.key}={self.value}"
        else:
            return self.value

    def has_a_key(self) -> bool:
        return len(self.key) > 0

    def has_value(self) -> bool:
        return len(self.value) > 0

    def add_elem(self, token: Token):
        if len(self.value) > 0 and token.type == tokenize.NAME:
            self.value += " "

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
