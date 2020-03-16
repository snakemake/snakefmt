from snakefmt import DEFAULT_LINE_LENGTH


class Formatter:
    """A class to control the formatting of a string/stream."""

    def __init__(self, line_length: int = DEFAULT_LINE_LENGTH):
        self._line_length = line_length

    @property
    def line_length(self) -> int:
        return self._line_length
