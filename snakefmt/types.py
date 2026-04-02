from tokenize import TokenInfo
from typing import Iterator

TAB = "    "  # PEP8, indentation will be coded as 4 spaces
COMMENT_SPACING = "  "  # PEP8, minimum of two spaces for inline comments


def line_nb(token: TokenInfo) -> int:
    return token.start[0]


def col_nb(token: TokenInfo) -> int:
    return token.start[1]


def not_empty(token: TokenInfo):
    return len(token.string) > 0 and not token.string.isspace()


TokenIterator = Iterator[TokenInfo]
