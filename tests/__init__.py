from io import StringIO
from snakefmt.parser.parser import Snakefile
from snakefmt.formatter import Formatter


def setup_formatter(snake: str):
    stream = StringIO(snake)
    smk = Snakefile(stream)
    return Formatter(smk)
