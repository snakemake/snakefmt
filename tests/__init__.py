import logging
from io import StringIO
from pathlib import Path

from snakefmt.formatter import Formatter
from snakefmt.logging import LogConfig
from snakefmt.parser.parser import Snakefile


def setup_formatter(snake: str, line_length: int = None, black_config_file=None):
    stream = StringIO(snake)
    smk = Snakefile(stream)
    LogConfig.init(logging.DEBUG)
    return Formatter(smk, line_length=line_length, black_config_file=black_config_file)


class TestBase:
    def read_test_data(self, filename):
        with open(Path(__file__).parent / "test_data" / filename) as f:
            return f.read()

    def do_test(self, test_folder, line_length=88):
        test_folder = Path(test_folder)
        snakecode = self.read_test_data(test_folder / "input.smk")
        formatter = setup_formatter(snakecode, line_length)

        actual = formatter.get_formatted()
        expected = self.read_test_data(test_folder / "expected.smk")

        assert actual == expected
