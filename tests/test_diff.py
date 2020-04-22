from snakefmt.diff import Diff


class TestCompare:
    def test_empty_strings_returns_empty(self):
        original = ""
        new = ""
        diff = Diff()

        actual = diff.compare(original, new)
        expected = ""

        assert actual == expected

    def test_same_strings_returns_empty(self):
        original = "foo\n    bar"
        new = "foo\n    bar"
        diff = Diff()

        actual = diff.compare(original, new)
        expected = ""

        assert actual == expected

    def test_strings_differ_by_one_char_compact(self):
        original = "foo\n    bar"
        new = "foo\n    baz"
        diff = Diff(compact=True)

        actual = diff.compare(original, new)
        expected = (
            "--- original\n" "+++ new\n" "@@ -1,2 +1,2 @@\n" " foo\n" "-    bar+    baz"
        )

        assert actual == expected

    def test_strings_differ_by_one_empty_line_compact(self):
        original = "foo\n    bar\n"
        new = "foo\n    baz"
        diff = Diff(compact=True)

        actual = diff.compare(original, new)
        expected = (
            "--- original\n"
            "+++ new\n"
            "@@ -1,2 +1,2 @@\n"
            " foo\n"
            "-    bar\n"
            "+    baz"
        )

        assert actual == expected

    def test_strings_differ_by_one_char_non_compact(self):
        original = "foo\n    bar"
        new = "foo\n    baz"
        diff = Diff(compact=False)

        actual = diff.compare(original, new)
        expected = "  foo\n-     bar?       ^\n+     baz?       ^\n"

        assert actual == expected

    def test_strings_differ_compact_only_context_lines_returned(self):
        original = "line0\nline1\nline2\nfoo\n    bar\nline3\nline4\nline5\nline6"
        new = "line0\nline1\nline2\nfoo\n    baz\nline3\nline4\nline5\nline6"
        diff = Diff(compact=True, context_lines=1)

        actual = diff.compare(original, new)
        expected = (
            "--- original\n"
            "+++ new\n"
            "@@ -4,3 +4,3 @@\n"
            " foo\n"
            "-    bar\n"
            "+    baz\n"
            " line3\n"
        )

        assert actual == expected


class TestIsChanged:
    def test_same_strings_compact_returns_false(self):
        original = "foo\n    bar\n\n"
        new = "foo\n    bar\n\n"
        diff = Diff(compact=True)

        assert not diff.is_changed(original, new)

    def test_same_strings_non_compact_returns_false(self):
        original = "foo\n    bar"
        new = "foo\n    bar"
        diff = Diff(compact=False)

        assert not diff.is_changed(original, new)

    def test_different_strings_compact_returns_false(self):
        original = "foo\n    bar"
        new = "foo\n    baz"
        diff = Diff(compact=True)

        assert diff.is_changed(original, new)

    def test_different_strings_non_compact_returns_false(self):
        original = "foo\n    bar\n"
        new = "foo\n    bar"
        diff = Diff(compact=True)

        assert diff.is_changed(original, new)
