import pytest

from snakefmt.blocken import (
    FunctionClassBlock,
    GlobalBlock,
    IfForTryWithBlock,
    PythonBlock,
    consume_fstring,
    TokenIterator,
    tokenize,
    is_fstring_start,
    UnsupportedSyntax,
    parse,
)


def generate_tokens(input: str):
    return list(
        tokenize.generate_tokens(iter(input.splitlines(keepends=True)).__next__)
    )


class TestTokenIterator:
    def test_fstring1(self):
        input = 'f"hello world"'
        tokens = generate_tokens(input)
        token_iter = TokenIterator("", iter(tokens))
        # region test the classic useage of `consume_fstring`,
        #  togather with `is_fstring_start`
        for t in token_iter:
            if is_fstring_start(t):
                contents = consume_fstring(token_iter)
                break
        # endregion test
        assert t == tokens[0]
        assert contents == tokens[1:-2]
        assert [i.type for i in contents] == [
            tokenize.FSTRING_MIDDLE,
            tokenize.FSTRING_END,
        ]

    def test_fstring_with_bracket(self):
        input = 'a = f"hello {world}"'
        tokens = generate_tokens(input)
        token_iter = TokenIterator("", iter(tokens))
        for t in token_iter:
            if is_fstring_start(t):
                contents = consume_fstring(token_iter)
                assert t == tokens[2]
                assert contents == tokens[3:-2]
                assert [i.type for i in contents] == [
                    tokenize.FSTRING_MIDDLE,
                    tokenize.OP,
                    tokenize.NAME,
                    tokenize.OP,
                    tokenize.FSTRING_END,
                ]
                break

    def test_consum_all(self):
        input = "sth"
        tokens = generate_tokens(input)
        token_iter = TokenIterator("", iter(tokens))
        with pytest.raises(UnsupportedSyntax):
            for t in token_iter:
                pass
        assert t.type == tokenize.ENDMARKER

    example1 = (
        "def f():\n"  #
        "    return 1\n"
        "\n"
        "\n"
        "b = f'''\n"
        "{b =} f'''\n"
        "# comment\n"
        "with d: # comment\n"
        "   pass"
    )

    def test_next_new_line(self):
        tokens = generate_tokens(self.example1)
        token_iter = TokenIterator("", iter(tokens))
        # return: `def f():`
        head_empty_lines, indents, contents, token = token_iter.next_new_line()
        assert head_empty_lines == indents == []
        assert contents == tokens[:5]
        assert [i.string for i in contents] == ["def", "f", "(", ")", ":"]
        assert {token.line} == {t.line for t in contents}
        # return: `return 1` with indent
        head_empty_lines, indents, contents, token = token_iter.next_new_line()
        assert head_empty_lines == []
        assert indents == [tokens[6]]
        assert contents == tokens[7:9]
        assert [i.string for i in contents] == ["return", "1"]
        assert {token.line} == {t.line for t in contents}
        # return: the full `b = f'''\n...` f-string, with dedent and empty lines
        head_empty_lines, indents, contents, token = token_iter.next_new_line()
        assert head_empty_lines == tokens[10:12]
        assert indents == [tokens[12]]
        assert contents == tokens[13:23]
        assert [i.string for i in contents] == [
            *("b", "=", "f'''", "\n", "{", "b", "=", "}", " f", "'''")
        ]
        assert token.line == contents[-1].line
        # return: `with d:`, with empty lines and inline comment
        head_empty_lines, indents, contents, token = token_iter.next_new_line()
        assert head_empty_lines == tokens[24:26]
        assert indents == []
        assert contents == tokens[26:30]
        assert [i.string for i in contents] == ["with", "d", ":", "# comment"]
        assert {token.line} == {t.line for t in contents}
        # return: `pass`, with indent but no `\n` at the end
        head_empty_lines, indents, contents, token = token_iter.next_new_line()
        assert head_empty_lines == []
        assert indents == [tokens[31]]
        assert contents == tokens[32:33]
        assert [i.string for i in contents] == ["pass"]
        assert {token.line} == {t.line for t in contents}
        assert token.string == "" and token.type == tokenize.NEWLINE
        # return: the ENDMARKER, with dedent and no content
        head_empty_lines, indents, contents, token = token_iter.next_new_line()
        assert head_empty_lines == contents == []
        assert indents == [tokens[34]]
        assert token == tokens[35] == tokens[-1]
        assert token.type == tokenize.ENDMARKER

    example2 = (
        "def components(self):\n"  #
        "    this_symbol: DocumentSymbol = DocumentSymbol(\n"
        "        name=self.name,\n"
        "        detail='\\n'.join(i.rstrip() for i in self.block_lines()).strip('\\n'),\n"
        "        symbol_kind=self._keyword(),\n"
        "        position_start=self.start_token.start,\n"
        "        position_end=self.head_tokens[-1].end,\n"
        "        block=self,\n"
        "    )\n"
        "    yield this_symbol\n"
    )

    def test_next_component(self):
        tokens = generate_tokens(self.example2)
        token_iter = TokenIterator("", iter(tokens))
        index = 0

        def _check_single_component(*components: str):
            nonlocal index
            for string in components:
                contents = token_iter.next_component()
                assert contents == tokens[index : index + 1]
                assert [i.string for i in contents] == [string]
                index += 1

        _check_single_component("def", "components")
        contents = token_iter.next_component()
        assert contents == tokens[2:5]
        assert [i.string for i in contents] == ["(", "self", ")"]
        index = 5
        _check_single_component(
            *(":", "\n"),
            *("    ", "this_symbol", ":", "DocumentSymbol", "=", "DocumentSymbol"),
        )
        contents = token_iter.next_component()
        assert contents == tokens[13:][:73]
        assert [i.string for i in contents] == [
            *("(", "\n"),
            *("name", "=", "self", ".", "name", ",", "\n"),
            *("detail", "=", "'\\n'", ".", "join", "("),
            *("i", ".", "rstrip", "(", ")"),
            *("for", "i", "in", "self", ".", "block_lines", "(", ")"),
            *(")", ".", "strip", "(", "'\\n'", ")", ",", "\n"),
            *("symbol_kind", "=", "self", ".", "_keyword", "(", ")", ",", "\n"),
            "position_start",
            *("=", "self", ".", "start_token", ".", "start", ",", "\n"),
            *("position_end", "=", "self", ".", "head_tokens", "["),
            *("-", "1", "]", ".", "end", ",", "\n"),
            *("block", "=", "self", ",", "\n"),
            ")",
        ]
        index = 86
        _check_single_component("\n", "yield", "this_symbol", "\n", "")
        contents = token_iter.next_component()
        assert contents == tokens[91:][:1] == tokens[-1:]

    example3 = (
        "with a as b:\n"  #
        "    b\n"
        "    # 0\n"
        "    while c:\n"
        "        d\n"
        "        # 1\n"
        "           # 2\n"
        "\n"
        "      # 3\n"
        "         # 4\n"
        "       \n"
        "  # 5\n"
        "     # 6\n"
        "7# 7\n"
        "\n"
    )

    def test_next_block(self):
        tokens = generate_tokens(self.example3)
        assert [i for i, t in enumerate(tokens) if t.type == tokenize.INDENT] == [6, 15]
        # from the first line to the last content line
        lines, tail_noncoding = TokenIterator("", iter(tokens[3:])).next_block()
        contents = [t for line in lines for t in line.iter] + tail_noncoding
        assert contents[0].line == "with a as b:\n"
        assert contents == tokens[3:][:35]
        assert contents[-1].type == tokenize.NL
        assert contents[-2].type == tokenize.NEWLINE
        assert contents[-2].line == "7# 7\n"
        # from the second line, to the last line before
        #  `  # 5\n`, whose indent out of the block
        lines, tail_noncoding = TokenIterator("", iter(tokens[6:])).next_block()
        contents = contents_ = [t for line in lines for t in line.iter] + tail_noncoding
        assert contents[0].line == "    b\n" and contents[0].type == tokenize.INDENT
        assert contents == tokens[6:][:22] + tokens[32:][:2]
        assert {t.type for t in contents[-2:]} == {tokenize.DEDENT}
        assert contents[:-2][-1].line == "       \n"
        # even skip the heading indent, block ends at the same line
        lines, tail_noncoding = TokenIterator("", iter(tokens[7:])).next_block()
        contents = [t for line in lines for t in line.iter] + tail_noncoding
        assert contents == contents_[1:]
        # so does the COMMENT line
        lines, tail_noncoding = TokenIterator("", iter(tokens[9:])).next_block()
        contents = [t for line in lines for t in line.iter] + tail_noncoding
        assert contents[0].line == "    # 0\n" and contents[0].type == tokenize.COMMENT
        assert contents == contents_[3:]
        # enter the third block: exit before `      # 3\n` with 1 DEDENT only
        lines, tail_noncoding = TokenIterator("", iter(tokens[15:])).next_block()
        contents = [t for line in lines for t in line.iter] + tail_noncoding
        assert contents[0].line == "        d\n" and tokens[14].type == tokenize.NEWLINE
        assert contents == tokens[15:][:8] + tokens[32:][:1]
        assert [t.type for t in contents[-4:]] == [
            *(tokenize.COMMENT, tokenize.NL, tokenize.NL, tokenize.DEDENT)
        ]
        assert contents[-4].line == contents[-3].line == "           # 2\n"
        assert contents[-2].line == "\n"


class TestBlock:
    example1 = (
        "def f():\n"  #
        "    return 1\n"
        "\n"
        "\n"
        "b = f'''\n"
        "{b =} f'''\n"
        "# comment\n"
        "with d: # comment\n"
        "   pass"
    )

    def test_parse_python_block(self):
        block = parse(self.example1)
        assert "".join(block.full_linestrs) == self.example1
        assert isinstance(block, GlobalBlock)
        assert not block.head_lines
        assert not block.tail_noncoding
        assert (
            {block.deindent_level}
            == {i.deindent_level for i in block.body_blocks}
            == {0}
        )
        assert ["".join(i.full_linestrs) for i in block.body_blocks] == [
            "def f():\n    return 1\n\n\n",
            "b = f'''\n{b =} f'''\n",
            "# comment\nwith d: # comment\n   pass",
            "",
        ]
        fun1 = block.body_blocks[0]
        assert isinstance(fun1, FunctionClassBlock)
        assert [i.string for i in fun1.colon_line.body] == ["def", "f", "(", ")", ":"]
        assert [tuple(i) for i in fun1.tail_noncoding] == [
            (tokenize.NL, "\n", (3, 0), (3, 1), "\n"),
            (tokenize.NL, "\n", (4, 0), (4, 1), "\n"),
            (tokenize.DEDENT, "", (5, 0), (5, 0), "b = f'''\n"),
        ]
        assert ["".join(i.full_linestrs) for i in fun1.body_blocks] == [
            "    return 1\n"
        ]
        fun11 = fun1.body_blocks[0]
        assert isinstance(fun11, PythonBlock)
        assert [line.linestrs for line in fun11.head_lines] == [["    return 1\n"]]
        assert not fun11.body_blocks
        assert not fun11.tail_noncoding
        if3 = block.body_blocks[2]
        assert isinstance(if3, IfForTryWithBlock)
        assert [i.string for i in if3.colon_line.body] == [
            *("with", "d", ":", "# comment"),
        ]
        assert not if3.tail_noncoding
        assert ["".join(i.full_linestrs) for i in if3.body_blocks] == ["   pass"]
        if31 = if3.body_blocks[0]
        assert isinstance(if31, PythonBlock)
        assert [line.linestrs for line in if31.head_lines] == [["   pass"]]
        assert not if31.body_blocks
        assert [tuple(i) for i in if31.tail_noncoding] == [
            (tokenize.DEDENT, "", (10, 0), (10, 0), "")
        ]
