from pathlib import Path

import toml

from snakefmt import DEFAULT_LINE_LENGTH


class Formatter:
    """A class to control the formatting of a string/stream."""

    def __init__(self, line_length: int = DEFAULT_LINE_LENGTH):
        self._line_length = line_length

    def __eq__(self, other) -> bool:
        if isinstance(other, self.__class__):
            return self.__dict__ == other.__dict__
        else:
            return False

    @property
    def line_length(self) -> int:
        return self._line_length

    @staticmethod
    def from_config(config_path: Path) -> "Formatter":
        config = toml.loads(config_path.read_text())
        tools = config.get("tool", {})
        snakefmt_opts = tools.get("snakefmt", {})
        try:
            line_length = int(snakefmt_opts["line_length"])
        except KeyError:
            line_length = int(
                tools.get("black", {}).get("line_length", DEFAULT_LINE_LENGTH)
            )
        return Formatter(line_length=line_length)
