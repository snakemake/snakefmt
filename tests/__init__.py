from io import StringIO

from snakefmt.formatter import Formatter
from snakefmt.parser.parser import Snakefile


def setup_formatter(snake: str, line_length: int = None, black_config_file=None):
    stream = StringIO(snake)
    smk = Snakefile(stream)
    return Formatter(smk, line_length=line_length, black_config_file=black_config_file)
