import runpy
import sys
from unittest import mock


def test_main():
    with mock.patch("snakefmt.snakefmt.main", return_value=0) as mock_main:
        with mock.patch.object(sys, "argv", ["snakefmt"]):
            try:
                runpy.run_module("snakefmt.__main__", run_name="__main__")
            except SystemExit as e:
                assert e.code == 0
            mock_main.assert_called_once()
