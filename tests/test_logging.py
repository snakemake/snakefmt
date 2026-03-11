import logging

from tests import setup_formatter


class TestLogging:
    def test_warning_line_number_reported_on_formatted_file(self, caplog):
        """https://github.com/snakemake/snakefmt/issues/241"""
        # Ensure we capture logs from 'snakefmt'
        caplog.set_level(logging.WARNING, logger="snakefmt")

        snakecode = (
            "# some things here to cause blank lines to be inserted\n"
            "def my_function():\n"
            "    return 1\n"
            "rule call_variants:\n"
            "    input:\n"
            "        some_file,\n"
            "        # some comment\n"
        )
        # Original line numbers:
        # 1: # some things here to cause blank lines to be inserted
        # 2: def my_function():
        # 3:     return 1
        # 4: rule call_variants:
        # 5:     input:
        # 6:         some_file,
        # 7:         # some comment

        # Formatted output expected:
        # 1: # some things here to cause blank lines to be inserted
        # 2: def my_function():
        # 3:     return 1
        # 4:
        # 5:
        # 6: rule call_variants:
        # 7:     input:
        # 8:         some_file,
        # 9:         # some comment

        formatter = setup_formatter(snakecode)
        formatter.get_formatted()

        warnings = [rec.message for rec in caplog.records]

        assert any(
            "at line 7" in w for w in warnings
        ), f"Warning should report line 7, but got: {warnings}"
