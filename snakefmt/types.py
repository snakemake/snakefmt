from typing import Iterator, NamedTuple, Tuple

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
