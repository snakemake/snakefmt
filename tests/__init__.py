from io import StringIO

from snakefmt import DEFAULT_LINE_LENGTH
from snakefmt.formatter import Formatter
from snakefmt.parser.parser import Snakefile


def setup_formatter(snake: str, line_length: int = DEFAULT_LINE_LENGTH):
    stream = StringIO(snake)
    smk = Snakefile(stream)
    return Formatter(smk, line_length=line_length)
