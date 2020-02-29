from snakefmt.snakefmt import construct_regex


class TestConstructRegex:
    def test_noNewline_returnsCompiledRegex(self):
        regex = ""
