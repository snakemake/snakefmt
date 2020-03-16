from snakefmt.formatter import Formatter


def test_line_length():
    line_length = 5
    fmt = Formatter(line_length=line_length)

    actual = fmt.line_length
    expected = line_length

    assert actual == expected
