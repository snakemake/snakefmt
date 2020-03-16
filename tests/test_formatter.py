from io import StringIO
from pathlib import Path
from unittest import mock

import pytest

from snakefmt.formatter import Formatter


def test_line_length():
    line_length = 5
    fmt = Formatter(line_length=line_length)

    actual = fmt.line_length
    expected = line_length

    assert actual == expected


class TestEquality:
    def test_same_returnsTrue(self):
        assert Formatter() == Formatter()

    def test_different_returnsFalse(self):
        assert not Formatter() == Formatter(line_length=0)


class TestFromConfig:
    @mock.patch("pathlib.Path.read_text", return_value="")
    def test_emptyConfig_returnsDefault(self, mock):
        config = Path("pyproject.toml")

        actual = Formatter.from_config(config)
        expected = Formatter()

        assert actual == expected

    @mock.patch("pathlib.Path.read_text", return_value="[tool.foo]\nbar=true")
    def test_configWithNoSnakfmtSection_returnsDefault(self, mock):
        config = Path("pyproject.toml")

        actual = Formatter.from_config(config)
        expected = Formatter()

        assert actual == expected

    @mock.patch("pathlib.Path.read_text", return_value="[tool.black]\nline_length=1000")
    def test_configWithOnlyBlackSection_returnsBlackParams(self, mock):
        config = Path("pyproject.toml")

        actual = Formatter.from_config(config)
        expected = Formatter(line_length=1_000)

        assert actual == expected

    @mock.patch(
        "pathlib.Path.read_text",
        return_value="[tool.black]\nline_length=1\n[tool.snakefmt]\nline_length=5",
    )
    def test_configWithSnakefmtAndBlackSection_returnsSnakefmtParams(
        self, mock: mock.MagicMock
    ):
        config = Path("pyproject.toml")

        actual = Formatter.from_config(config)
        expected = Formatter(line_length=5)

        assert actual == expected


class TestFormat:
    def test_emptyInput_emptyOutput(self):
        stream = StringIO()
        formatter = Formatter()

        actual = formatter.format(stream)
        expected = ""

        assert actual == expected

    @pytest.mark.xfail(reason="We currently force newline after every level 0 keyword")
    def test_configfileLineWithSingleQuotes_returnsDoubleQuotes(self):
        stream = StringIO("configfile: 'foo.yaml'")
        formatter = Formatter()

        actual = formatter.format(stream)
        expected = 'configfile: "foo.yaml"'

        assert actual == expected
