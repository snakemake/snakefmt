import io
import tokenize
from functools import singledispatch
from tokenize import TokenInfo
from typing import Iterable

from snakefmt.config import Mode
from snakefmt.formatter import black
from snakefmt.formatter.shell import format_python_string_literal
from snakefmt.formatter.state import FormatState
from snakefmt.parser.blocks import Block, PythonBlock
from snakefmt.parser.grammar import Module, Rule, SnakemakeDirectiveBlock, UseRule
from snakefmt.parser.snakemake_blocks import (
    PythonArgumentsBlock,
    SnakemakeArgumentsBlock,
    SnakemakeBlock,
    SnakemakeExecutableBlock,
    SnakemakeInlineArgumentBlock,
)
from snakefmt.parser.tokens import TAB, deindent_lines, tokens2linestrs


@singledispatch
def format_block(block: Block, mode: Mode, state: FormatState) -> str:
    """Format a whole block to source text (was `Block.formatted`)."""
    raise NotImplementedError(f"No formatter for {type(block).__name__}")


@format_block.register
def _(block: PythonBlock, mode: Mode, state: FormatState) -> str:
    raw = "".join(block.full_linestrs)
    if not raw.strip():
        return ""
    return black.format_python(
        raw, mode, block.deindent_level, start_token=block.head_lines[0].body[0]
    )


@format_block.register
def _(block: SnakemakeBlock, mode: Mode, state: FormatState) -> str:
    formatted_prior, post_colon = format_head(block, mode)
    formatted_body = format_body(block, mode, state, post_colon)
    return "".join([formatted_prior, formatted_body])


def format_head(block: SnakemakeBlock, mode: Mode) -> tuple[str, list[TokenInfo]]:
    """Format the head line, up to and including the colon.

    Parameters (inline included) live in `body_blocks`, so no post-colon
    tokens are returned; a trailing comment on the colon line is kept here.
    """
    indent = TAB * block.deindent_level
    source_line = block.head_source_line()
    if FormatState.found_skip(source_line):
        return indent + source_line.lstrip(), []
    prior_colon, post_colon = block.split_colon_line()
    assert len(prior_colon) == 1, "Snakemake keywords should be in one line"
    (head,) = prior_colon
    components = head.strip().split()
    formatted_head = indent + " ".join(components) + ":"
    if block.colon_line.end_op == ":":
        # only a single line comment or empty is possible here, add directly
        colon_token = next(post_colon)
        post = tokens2linestrs(post_colon.rest)
        if post:
            post[0] = post[0][colon_token.end[1] :]
            fake_str = "if 1:" + "".join(post) + "   ..."
            fake_fmt = black.format_python(fake_str, mode).strip()
            formatted_head += fake_fmt.split(":", 1)[1].rsplit("\n", 1)[0]
    return formatted_head + "\n", []


@singledispatch
def format_body(
    block: SnakemakeBlock, mode: Mode, state: FormatState, post_colon: list[TokenInfo]
) -> str:
    """Format a block's body (was `SnakemakeBlock.format_body`)."""
    raise NotImplementedError(f"No body formatter for {type(block).__name__}")


def _format_arguments_body(
    block: SnakemakeArgumentsBlock,
    mode: Mode,
    state: FormatState,
    post_colon: list[TokenInfo],
) -> str:
    """Format the parameters, positional before keyword, one per line."""
    if state.found_skip(block.head_source_line()):
        return "".join(block.argument.full_linestrs)
    return format_post_colon(
        block.argument, mode, block.deindent_level, block.trailing_comma
    )


format_body.register(_format_arguments_body)


@format_block.register
def _(block: SnakemakeInlineArgumentBlock, mode: Mode, state: FormatState) -> str:
    """Try to merge the inline argument into the head line.
    If the line is too long after merging, then keep them separate.
    """
    formatted_prior, post_colon = format_head(block, mode)
    formatted_body = format_body(block, mode, state, post_colon)
    formatted = [formatted_prior, formatted_body]
    if formatted_body.count("\n") == 1 and formatted_body.endswith("\n"):
        if formatted_prior.count("\n") > 1:
            prev, last_head_line = formatted_prior[:-1].rsplit("\n", 1)
            prev += "\n"
        else:
            prev, last_head_line = "", formatted_prior[:-1]
        if formatted_prior.endswith(":\n") and "#" not in last_head_line:
            formatted_merge = last_head_line + " " + formatted_body.lstrip()
            if len(formatted_merge) <= mode.line_length:
                formatted = [prev + formatted_merge]
    return "".join(formatted)


@format_body.register
def _(
    block: SnakemakeExecutableBlock,
    mode: Mode,
    state: FormatState,
    post_colon: list[TokenInfo],
) -> str:
    assert not post_colon, "python must start on a new line"
    (param_space,) = block.body_blocks
    assert isinstance(param_space, PythonBlock), "Unexpected body block type"
    return format_block(param_space, mode, state)


@format_body.register
def _(
    block: SnakemakeDirectiveBlock,
    mode: Mode,
    state: FormatState,
    post_colon: list[TokenInfo],
) -> str:
    """Sort directives in the order of subautomata,
    and format them together with the head line.
    """
    assert not post_colon, "Invalid inline contents"
    formatted: list[str] = []
    directives: dict[str, str] = {}
    tail_noncoding: list[str] = []
    indent = TAB * (block.deindent_level + 1)
    order = state.module_order if isinstance(block, Module) else state.rule_order
    for sub in block.body_blocks:
        assert not tail_noncoding, "no tail_noncoding before body_blocks"
        if isinstance(sub, PythonBlock):
            formatted.append(format_block(sub, mode, state))
            for line in sub.head_linestrs:
                state = state.update(line.lstrip())
            # A blank line the user wrote between the docstring
            # and the first directive is kept
            if len(block.body_blocks) > 1:
                sub = block.body_blocks[1]
                assert isinstance(
                    sub, SnakemakeBlock
                ), "Unexpected block type in snakemake keyword block"
                following = sub.colon_line.head_noncoding
                if following and following[0].type == tokenize.NL:
                    formatted.append("\n")
            continue
        assert isinstance(
            sub, SnakemakeBlock
        ), "Unexpected block type in snakemake keyword block"
        noncoding = tokens2linestrs(iter(sub.colon_line.head_noncoding))
        directive = ""
        for line in noncoding:  # here noncoding is already formated
            linelstrip = line.lstrip()
            last_sort_off = state.sort_directives
            if linelstrip:
                # only non-empty lines are formattable
                if state.found_skip(linelstrip):
                    directive += line
                else:
                    directive += indent + black.format_python(linelstrip, mode, 0)
                state = state.update(linelstrip)
            if state.not_format:
                if directives:
                    formatted.extend(
                        sort_directives(directives, order, block.subautomata)
                    )
                if directive:
                    formatted.append(directive)
                    directive = ""
                if not linelstrip:
                    formatted.extend(
                        deindent_lines(sub.indent_str, block.deindent_level + 1, [line])
                    )
            elif not state.sort_directives:
                if directives:
                    formatted.extend(
                        sort_directives(directives, order, block.subautomata)
                    )
                if directive:
                    formatted.append(directive)
                    directive = ""
            elif not last_sort_off:
                # state.sort_directives switched on, this comment is
                #  actually `# fmt: on[sort]` directive,
                # so split from next directive
                formatted.append(directive)
                directive = ""
        if state.not_format:
            formatted.extend(
                deindent_lines(
                    sub.indent_str,
                    block.deindent_level + 1,
                    sub.raw_source_linestrs(),
                )
            )
        else:
            directive += format_block(sub, mode, state)
            if state.sort_directives:
                directives[sub.start_token.string] = directive
            else:
                assert not directives, "Already flushed once fmt: off[sort]"
                formatted.append(directive)
        if sub.tail_noncoding:
            tail_noncoding = tokens2linestrs(iter(sub.tail_noncoding))
        # no `\n` between
    if directives:
        formatted.extend(sort_directives(directives, order, block.subautomata))
    if tail_noncoding:
        tail_noncoding = [i.lstrip().rstrip("\n") for i in tail_noncoding]
        formatted.extend(f"{indent}{i}\n" for i in tail_noncoding if i)
    return "".join(formatted)


def sort_directives(
    directives: dict[str, str], order: Iterable[str] = (), default: Iterable[str] = ()
) -> Iterable[str]:
    """Yield the directives sorted by `order`. Clears `directives`."""
    for keyword in order:
        if keyword in directives:
            yield directives.pop(keyword)
    if directives:
        for keyword in default:
            if keyword in directives:
                yield directives.pop(keyword)
    assert not directives, f"Unknown directives: {', '.join(directives)}"


@format_block.register
def _(block: UseRule, mode: Mode, state: FormatState) -> str:
    """Allow:
    use rule * from other_workflow exclude ruleC as other_*
    use rule * from other_workflow exclude ruleC
    use rule * from other_workflow as other_*
    use rule * from other_workflow
    use rule a,b from other_workflow
    """
    assert len(block.head_lines) == 1, "use directive should only have one head line"
    head_line = tokens2linestrs(iter(block.head_lines[0].body))
    assert len(head_line) == 1, "use directive should be single line"
    head_bulk_line = head_line[0].split("#", 1)[0]
    if ":" not in head_bulk_line:
        # return quickly (also no body block here)
        indent = TAB * block.deindent_level
        components = head_bulk_line.strip().split()
        formatted_head = indent + " ".join(components)
        if "#" in head_line[0]:
            formatted_head += "  " + black.format_python(
                "#" + head_line[0].split("#", 1)[1], mode=mode
            ).rstrip("\n")
        return formatted_head + "\n"
    formatted_prior, post_colon = format_head(block, mode)
    formatted_body = format_body(block, mode, state, post_colon)
    return "".join([formatted_prior, formatted_body])


@format_body.register
def _(
    block: Rule.Shell, mode: Mode, state: FormatState, post_colon: list[TokenInfo]
) -> str:
    """Format the body, then (if enabled) reformat its lone string
    literal as shell code with `shfmt`.

    Going through the normal body formatting first keeps surrounding
    comments/blank lines and the trailing-comma handling; only the
    literal itself is then swapped for its `shfmt`'ed form.
    """
    formatted = _format_arguments_body(block, mode, state, post_colon)
    if not state.format_shell:
        return formatted
    strings = [
        token
        for token in tokenize.generate_tokens(io.StringIO(formatted).readline)
        if token.type == tokenize.STRING
    ]
    if len(strings) != 1:
        return formatted
    (string,) = strings
    lines = formatted.splitlines(keepends=True)
    start = sum(len(line) for line in lines[: string.start[0] - 1]) + string.start[1]
    end = sum(len(line) for line in lines[: string.end[0] - 1]) + string.end[1]
    return (
        formatted[:start]
        + format_python_string_literal(formatted[start:end], block.deindent_level + 1)
        + formatted[end:]
    )


def format_post_colon(
    block: PythonArgumentsBlock, mode: Mode, deindent_level: int, trailing_comma=True
) -> str:
    """If there is indent after the colon line,
    even if expressions exist in that line,
    indent body should be formatted as part of the cotent:
        input: balabal,  # <- expression after the colon
            balabal2     # <- indent body, should format as part of the content
    to:
        input:
            balabal,
            balabal2,

    Morover, the original snakefmt allow sort positional arguments
      before keyword arguments. Here need check, too

    Input:
        post_colon: tokens after the colon in the head line,
                e.g. `balabal,` in the above example
            post_colon[0] := TokenInfo(type=NAME, string='balabal', ...)
        body_blocks: indent body blocks,
                e.g. the block of `balabal2` in the above example
    """
    first = next(block.iter, None)
    if first is None:
        return ""
    lines: dict[int, str] = {}
    for token in block.iter:
        lines.update(
            zip(
                range(token.start[0], token.end[0] + 1),
                token.line.splitlines(keepends=True),
            )
        )
    if not lines:
        return ""

    def source(start: tuple[int, int], end: tuple[int, int]) -> str:
        """The block source text between two (line, col) positions, half-open."""
        if start[0] == end[0]:
            return lines[start[0]][start[1] : end[1]]
        text = lines[start[0]][start[1] :]
        for row in range(start[0] + 1, end[0]):
            text += lines[row]
        text += lines[end[0]][: end[1]]
        return text

    # Collect, in source order, everything between the previous parameter's
    # end and this one's end (so nothing in between is lost).
    start = first.start
    slices: list[tuple] = []
    for param in block.params:
        if not param.tokens:
            continue
        end = param.tokens[-1].end
        slices.append((param, source(start, end)))
        start = end

    # positional (unnamed) before keyword
    slices.sort(key=lambda param_text: param_text[0].is_keyword)

    parts = []
    for param, text in slices:
        if trailing_comma != param.has_comma:
            if trailing_comma:
                text += "\n,"
            else:
                text = text.rstrip(",")
        parts.append(text)
    parts.append(source(start, token.end))
    tail_noncoding = "".join(tokens2linestrs(iter(block.tail_noncoding)))
    formatable = "".join(parts) + tail_noncoding
    return black.format_python(
        formatable,
        mode,
        deindent_level,
        partial="(",
        start_token=first,
    )
