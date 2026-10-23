import re
import tokenize
from tokenize import TokenInfo
from typing import Iterable

from snakefmt.exceptions import (
    ColonError,
    EmptyContextError,
    EndOfInput,
    InvalidParameter,
    InvalidParameterSyntax,
    NewlineError,
    NoParametersError,
    NotAnIdentifierError,
    SyntaxFormError,
    TooManyParameters,
    UnsupportedSyntax,
)
from snakefmt.parser.blocks import ColonBlock, PythonBlock
from snakefmt.parser.tokens import (
    TokenIterator,
    effective,
    is_op,
    line_nb,
    validate_parameters,
)


class SnakemakeBlock(ColonBlock):
    subautomata = {}
    deprecated = {}
    nameable = False
    """an optional identifier may precede the colon (`storage a:`, `input with:`)"""

    @property
    def start_token(self):
        token = super().start_token
        assert token is not None, "SnakemakeBlock should have a start_token"
        return token

    def validate_head(self, allow_suffix=False):
        """A keyword head is `<keyword> [<name>]:`, then a newline."""
        body = self.colon_line.body
        keyword = body[0].string
        for icolon, token in enumerate(body[1:], 1):
            if is_op(":", token):
                break
        else:
            ColonError(line_nb(body[-1]), body[-1].string, keyword)
        if icolon > 1:
            name = body[1]
            if self.nameable:
                if name.type != tokenize.NAME:
                    NotAnIdentifierError(line_nb(name), name.string, keyword)
                if icolon > 2:
                    name = body[2]
                else:
                    name = None
            if name is not None:
                if name.string == "with":
                    # a `with` suffix, accepted only where `nameable` marks it so
                    raise InvalidParameterSyntax(
                        f"'{keyword} with:' is not allowed in this context."
                    )
                else:
                    ColonError(line_nb(name), name.string, keyword)
        if not allow_suffix:
            for i in range(icolon + 1, len(body)):
                token = body[i]
                if effective(token):
                    NewlineError(line_nb(token), body[0].string)

    def consume(self, tokens):
        """Consume tokens until the end of the block head line (the line with `:`)"""
        self.validate_head()
        super().consume(tokens)

    def head_source_line(self) -> str:
        """Original source line of the head, for `# fmt: skip` detection."""
        return self.colon_line.body[0].line

    def raw_source_linestrs(self):
        """Source lines of the block, excluding leading (head_noncoding) comments."""
        yield self.head_source_line()
        for block in self.body_blocks:
            yield from block.full_linestrs


class Argument:
    """A single parameter.

    `tokens` are the parameter's expression tokens, ending with a top-level
    comma when the source had one. `tail` holds the comment(s) and newline that
    trail it (e.g. `"a",  # comment`), so `tokens` stays a clean expression.
    """

    def __init__(self, tokens: list[TokenInfo], tail: list[TokenInfo] | None = None):
        self.tokens = tokens
        self.tail = tail if tail is not None else []
        self.is_keyword = self._is_keyword()

    def _is_keyword(self) -> bool:
        body = self.tokens
        if not body:
            return False
        first = body[0]
        for i, token in enumerate(body[1:], 1):
            if token.string.strip() and not token.string.startswith("#"):
                if is_op("=", token):
                    if first.type != tokenize.NAME:
                        key = tokenize.untokenize(
                            [(t.type, t.string) for t in body[:i]]
                        ).strip()
                        raise InvalidParameterSyntax(
                            f"{line_nb(first)}Invalid key {key}"
                        )
                    return True
                break
        if is_op("**", first):
            return True
        if is_op("=", first):
            raise InvalidParameterSyntax(
                f"{line_nb(first)}Operator = used with no preceding key"
            )
        return False

    @property
    def has_comma(self) -> bool:
        return bool(self.tokens) and is_op(",", self.tokens[-1])

    @classmethod
    def from_token(cls, tokens: Iterable[TokenInfo]):
        """Split parameter tokens into `Argument`s.

        Parameters are delimited by top-level commas. Each region is handed to
        `_munch` (whole first, then maximal munch by lines). Comment-only lines
        belong to the previous argument, or to `head_noncoding` if none.
        """
        tokeniter = TokenIterator("", iter(tokens))
        process = True
        while process:
            metaarg: list[list[TokenInfo]] = []
            try:
                while True:
                    component = tokeniter.next_component()
                    metaarg.append(component)
                    if len(component) == 1 and is_op(",", component[0]):
                        break
            except EndOfInput:
                process = False
            if metaarg:
                yield from cls._munch(metaarg)

    @classmethod
    def _munch(cls, region: list[list[TokenInfo]]):
        """Split one comma-delimited region into `Argument`s.

        The whole region is tried first, so implicit string concatenation and
        operator continuations stay a single parameter. Only if the whole region
        is not one valid argument is it split by lines, taking the longest valid
        prefix each time (maximal munch).
        """
        current: list[TokenInfo] = []
        lines = [current]
        for component in region:
            if len(component) == 1:
                (token,) = component
                if not effective(token):
                    if token.type in (tokenize.NL, tokenize.NEWLINE):
                        if current:
                            current += component
                            current = []
                            lines.append(current)
                    # skip
                    continue
            current += component
        while lines:
            n = len(lines)
            while n:
                cand = [t for i in range(n) for t in lines[i]]
                if validate_parameters(cand):
                    if cand:
                        yield cls(cand)
                    lines = lines[n:]
                    break
                n -= 1
            else:
                flat = [token for line in lines for token in line if effective(token)]
                if not flat:
                    raise InvalidParameterSyntax("Invalid parameter")
                first = flat[0]
                if is_op("=", first):
                    raise InvalidParameterSyntax(
                        f"{line_nb(first)}Operator = used with no preceding key"
                    )
                for i, token in enumerate(flat[1:], 1):
                    if is_op("=", token):
                        if first.type != tokenize.NAME:
                            key = tokenize.untokenize(
                                [(t.type, t.string) for t in flat[:i]]
                            ).strip()
                            raise InvalidParameterSyntax(
                                f"{line_nb(first)}Invalid key {key}"
                            )
                        break
                raise InvalidParameterSyntax(
                    f"{line_nb(first)}Invalid parameter {first.line.strip()}"
                )


class PythonArgumentsBlock(PythonBlock):
    """Manage a directive's indent block and the parent's post-colon content,
    turning both into individual `Argument` parameters.
    """

    def __init__(
        self,
        deindent_level,
        tokens,
        lines=None,
        post_colon: list[TokenInfo] | None = None,
    ):
        super().__init__(deindent_level, tokens, lines)
        self.post_colon = list(post_colon or [])
        self.params = list(Argument.from_token(self.iter))

    @property
    def iter(self):
        """All parameter tokens: post-colon content and the indent body."""
        yield from self.post_colon
        for line in self.head_lines:
            yield from line.iter


class SnakemakeArgumentsBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `input:`, `output:`, etc.
    The content is one PythonArgument or multiple PythonArgument seperated by comma,
    """

    Argument = PythonArgumentsBlock

    @property
    def argument(self):
        assert len(self.body_blocks) == 1
        (block,) = self.body_blocks
        assert isinstance(block, self.Argument)
        return block

    def consume(self, tokens):
        """Split the parameter content into one `Argument` per parameter.

        The tokens after the colon (both inline and indented) are taken out of
        the head line and split into parameters, so each token appears exactly
        once. The original head line is kept as text for `fmt: off` verbatim
        output.
        """
        self.validate_head(allow_suffix=True)
        self.consume_body(tokens)

    def consume_body(self, tokens):
        colon = next(
            i for i, token in enumerate(self.colon_line.body) if is_op(":", token)
        )
        post_colon = self.colon_line.body[colon + 1 :]
        # comments right after the colon belong to the head line, not a parameter
        while post_colon and post_colon[0].type == tokenize.COMMENT:
            post_colon.pop(0)
        peeked: list[TokenInfo] = []
        for token in tokens:
            peeked.append(token)
            if token.type != tokenize.NL and token.type != tokenize.COMMENT:
                break
        tokens.denext(*reversed(peeked))
        if peeked[-1].type != tokenize.INDENT:
            lines, tail = [], []
        else:
            lines, tail = tokens.next_block()
        block = self.Argument(self.deindent_level + 1, tokens, lines, post_colon)
        block.extend_tail_noncoding(tail)
        self.body_blocks = [block]

    trailing_comma = True
    """whether the formatted list ends with a comma"""


class SnakemakeUnnamedArgumentsBlock(SnakemakeArgumentsBlock):

    def consume_body(self, tokens):
        super().consume_body(tokens)
        self.check_parameters()

    def check_parameters(self):
        if any(param.is_keyword for param in self.argument.params):
            token = self.start_token
            raise InvalidParameterSyntax(
                f"{line_nb(token)}{token.string} definition "
                f"does not accept key/value parameters"
            )


class SnakemakeUnnamedArgumentBlock(SnakemakeUnnamedArgumentsBlock):
    """Only one unnamed parameter; nothing splits it, so a string may be
    continued over several lines (`shell: "a"\n"b"`). No trailing comma.
    """

    trailing_comma = False

    def check_parameters(self):
        if not self.argument.params:
            token = self.start_token
            raise NoParametersError(f"{line_nb(token)}In {token.string} definition.")
        if len(self.argument.params) > 1:
            token = self.start_token
            raise TooManyParameters(
                f"{line_nb(token)}{token.string} definition expects a single parameter"
            )
        if self.argument.params[0].is_keyword:
            token = self.start_token
            raise InvalidParameter(
                f"{line_nb(token)}{token.string} definition requires a "
                f"positional (not key/value) parameter"
            )


class SnakemakeInlineArgumentBlock(SnakemakeUnnamedArgumentBlock):
    """Inform formatter to try to merge the inline argument into the head line.
    If the line is too long after merging, then keep them separate.
    """


class SnakemakeExecutableBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `run:`, `onstart:`, etc.
    The content is pure python, and must start from the next line after the colon.
    """

    def consume_body(self, tokens):
        lines, tail_noncoding = tokens.next_block()
        executable = PythonBlock(self.deindent_level + 1, tokens, lines)
        executable.extend_tail_noncoding(tail_noncoding)
        self.body_blocks.append(executable)


class SnakemakeDirectiveBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `rule:`, `module:`, etc.
    The contents are other snakemake blocks.
    """

    nameable = True

    def consume_body(self, tokens):
        blocks = self.consume_subblocks(tokens, ender_subblock=True)
        keyword = self.colon_line.body[0].string
        no_content = True
        seen_docstring = False
        seen_directive = False
        for block in blocks:
            if isinstance(block, SnakemakeBlock):
                no_content = False
                seen_directive = True
                continue
            if not isinstance(block, PythonBlock):
                rep = block.start_token or self.start_token
                raise UnsupportedSyntax(
                    f"{line_nb(rep)}Unexpected content in "
                    f"{keyword} block: {rep.line}"
                )
            code = [
                token
                for line in block.head_lines
                for token in line.iter
                if effective(token)
            ]
            if not code:
                continue
            if all(token.type == tokenize.STRING for token in code):
                if seen_directive or seen_docstring:
                    rep = code[0]
                    raise SyntaxError(
                        f"{line_nb(rep)}Unexpected docstring in "
                        f"{keyword} definition"
                    )
                seen_docstring = True
                no_content = False
                continue
            rep = block.start_token
            if rep is not None:
                if rep.type == tokenize.NAME:
                    raise SyntaxError(
                        f"{line_nb(rep)}Unrecognised keyword "
                        f"{rep.string!r} in {keyword} definition"
                    )
            else:
                rep = self.start_token
            raise SyntaxError(
                f"{line_nb(rep)}Invalid python code in "
                f"{keyword} definition: {rep.line}"
            )
        if no_content:
            raise EmptyContextError(
                f"{line_nb(self.colon_line.body[0])}{keyword} has no "
                f"keywords attached to it."
            )
        self.body_blocks = blocks


class Use(SnakemakeDirectiveBlock):
    """
    use rule ','.join(.whitelist)[ from .module[ exclude .exclude]][ as .rename][ with:]
    """

    _EBNF = (
        '"use" "rule" (identifier | "*") '
        '"from" identifier '
        '["exclude" identifier {"," identifier}] '
        '["as" identifier] ["with" ":"]'
    )

    def validate_head(self, allow_suffix=False):
        body = self.colon_line.body
        line = body[0].line.split("#", 1)[0].strip()

        def fail():
            raise SyntaxFormError(line_nb(body[0]), line, self._EBNF)

        def is_identifier(token: str):
            return re.fullmatch(r"[a-zA-Z_]\w*", token) is not None

        def is_glob(token: str):
            return re.fullmatch(r"[a-zA-Z_][\w*]*", token) is not None

        # commas may be surrounded by spaces; make them separate tokens
        tokens = line.replace(",", " , ").split()
        if tokens[:2] != ["use", "rule"]:
            fail()

        # reading a *required* token past the end is a syntax error, so those
        # reads are left unguarded and `IndexError` -> `fail()`. Optional
        # trailing parts (e.g. `from ...` alone) are guarded with `i < len`.
        try:
            whitelist = [tokens[2]]
            i = 3
            # the whitelist must be followed by a keyword, so running past the
            # end here is a syntax error (IndexError -> fail())
            while tokens[i] == ",":
                whitelist.append(tokens[i + 1])
                i += 2
            if whitelist != ["*"]:
                if "*" in whitelist:
                    raise InvalidParameterSyntax(
                        "'*' cannot be used with other rule names in the use directive"
                    )
                if not all(is_identifier(name) for name in whitelist):
                    fail()
            if tokens[i] not in ("from", "as", "with", "with:"):
                fail()

            # module: the source after `from`
            if tokens[i] == "from":
                i += 1
                module = tokens[i]
                if not is_identifier(module):
                    fail()
                i += 1
            else:
                module = None
        except IndexError:
            fail()

        # exclude: comma separated rule names after `exclude`
        token_length = len(tokens)
        exclude: list[str] = []
        rename = None
        try:
            # exclude: comma separated rule names after `exclude`
            if i < token_length and tokens[i] == "exclude":
                exclude.append(tokens[i + 1])
                i += 2
                while i < token_length and tokens[i] == ",":
                    exclude.append(tokens[i + 1])
                    i += 2
                if not all(is_identifier(name) for name in exclude):
                    fail()
            # modifier: the alias after `as`
            if i < token_length and tokens[i] == "as":
                rename = tokens[i + 1]
                if not is_glob(rename):
                    fail()
                i += 2
        except IndexError:
            fail()

        if "".join(tokens[i:]) not in ("", "with:"):
            fail()

        if module is None and rename is None:
            raise InvalidParameterSyntax(
                "use directive must specify a rule from a module or modify the rule"
            )

        self.whitelist = whitelist
        self.module = module
        self.exclude = exclude
        self.rename = rename
