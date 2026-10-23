import tokenize
from dataclasses import replace
from functools import singledispatch
from typing import Iterable

from snakefmt.config import Mode
from snakefmt.exceptions import UnsupportedSyntax
from snakefmt.formatter import black
from snakefmt.formatter.indent import TAB, deindent_lines
from snakefmt.formatter.shell import format_python_string_literal
from snakefmt.formatter.state import FormatState
from snakefmt.logging import Warnings
from snakefmt.parser.blocks import Block, PythonBlock
from snakefmt.parser.grammar import Module, Rule, UseRule
from snakefmt.parser.snakemake_blocks import (
    Argument,
    PythonArgumentsBlock,
    SnakemakeArgumentsBlock,
    SnakemakeBlock,
    SnakemakeDirectiveBlock,
    SnakemakeExecutableBlock,
    SnakemakeInlineArgumentBlock,
)
from snakefmt.parser.tokens import (
    TokenIterator,
    effective,
    is_fstring_start,
    line_nb,
    splitlines,
    tokens2linestrs,
)


@singledispatch
def format_block(block: Block, mode: Mode, state: FormatState) -> str:
    """Format a whole block to source text (was `Block.formatted`)."""
    raise NotImplementedError(f"No formatter for {type(block).__name__}")


def _deindent_lines(block: Block):
    """Use four-space indentation throughout.

    Black rejects a mix of the synthetic prefix's spaces and tabs from the source.
    """
    if block.start_token is None:
        return "".join(block.full_linestrs)
    return "".join(
        deindent_lines(block.indent_str, block.deindent_level, block.full_linestrs)
    )


@format_block.register
def _(block: PythonBlock, mode: Mode, state: FormatState) -> str:
    raw = _deindent_lines(block)
    if not raw.strip():
        return ""
    return black.format_python(
        raw, mode, block.deindent_level, start_token=block.start_token
    )


@format_block.register
def _(block: SnakemakeBlock, mode: Mode, state: FormatState) -> str:
    formatted_prior = format_head(block, mode)
    formatted_body = format_body(block, mode, state)
    return "".join([*formatted_prior, formatted_body])


@singledispatch
def format_head(block: SnakemakeBlock, mode: Mode) -> tuple[str, str]:
    """Format the head line, up to and including the colon.

    Parameters (inline included) live in `body_blocks`, so no post-colon
    tokens are returned; a trailing comment on the colon line is kept here.
    """
    indent = TAB * block.deindent_level
    source_line = block.head_source_line()
    if FormatState.found_skip(source_line):
        return indent + source_line.lstrip(), ""
    prior_colon, post_colon = block.split_colon_line()
    if len(prior_colon) != 1:
        raise UnsupportedSyntax("Snakemake keywords should be in one line")
    (head,) = prior_colon
    components = head.strip().split()
    formatted_head = indent + " ".join(components) + ":"
    head_comment = "\n"
    if block.colon_line.endswith_colon:
        # only a single line comment or empty is possible here, add directly
        colon_token = next(post_colon)
        post = tokens2linestrs(post_colon.rest)
        if post:
            post[0] = post[0][colon_token.end[1] :]
            head_comment = black.format_python("".join(post), mode, partial="#")
    return formatted_head, head_comment


@singledispatch
def format_body(block: SnakemakeBlock, mode: Mode, state: FormatState) -> str:
    """SnakemakeBlock specific, format components after colon
    including those after the colon in the head line and in the indent body blocks.
    """
    raise NotImplementedError(f"No body formatter for {type(block).__name__}")


def _format_arguments_body(
    block: SnakemakeArgumentsBlock, mode: Mode, state: FormatState
) -> str:
    """Format the parameters, positional before keyword, one per line."""
    if state.found_skip(block.head_source_line()):
        return _deindent_lines(block.argument)
    if any(i.string.strip() for i in block.argument.tail_noncoding):
        Warnings.block_comment_below(block.keyword, block.colon_line.body[0].start[0])
    return format_post_colon(
        block.argument, mode, block.deindent_level, block.trailing_comma
    )


format_body.register(_format_arguments_body)


@format_block.register
def _(block: SnakemakeInlineArgumentBlock, mode: Mode, state: FormatState) -> str:
    """Keep a single-parameter directive on one line when possible.

    - comment between keyword and parameter is moved above:
        ```
        threads:  # moved above
            4
        ```
        becomes
        ```
        # moved above
        threads: 4
        ```

    - comment after the parameter kept no matter the length:
        ```
        threads:
            4  # a very loooooooooooooooooog comment
        ```
        becomes
        ```
        threads: 4  # a very loooooooooooooooooog comment
        ```

    - If the value cannot fit on one line, it stays on its own indented lines:
        ```
        threads:
            lambda wildcards: a_very_long_expression_(
                wildcards, _that_will_not_fit_on_one_line
            )
        ```
    """

    head_code, head_comment = format_head(block, mode)
    formatted_body = format_body(block, mode, state)
    relocated: list[str] = []
    if not head_comment:  # FormatState.found_skip
        return head_code + head_comment + formatted_body
    if head_comment.strip():
        relocated.append(head_comment.strip())
    value_line = ""
    for line in splitlines(formatted_body):
        line = line.strip()
        if line.startswith("#"):
            relocated.append(line)
        else:
            if value_line:
                return head_code + head_comment + formatted_body
            value_line = line
    if relocated:
        Warnings.comment_relocation(block.keyword, block.colon_line.body[0].start[0])
    indent = TAB * block.deindent_level
    comments = "".join(f"{indent}{comment}\n" for comment in relocated)
    return f"{comments}{head_code} {value_line}\n"


@format_body.register
def _(block: SnakemakeExecutableBlock, mode: Mode, state: FormatState) -> str:
    if len(block.body_blocks) != 1 or not isinstance(block.body_blocks[0], PythonBlock):
        token = block.start_token
        raise UnsupportedSyntax(
            f"{line_nb(token)}Unexpected body block type in "
            f"{block.keyword} definition"
        )
    return format_block(block.body_blocks[0], mode, state)


@format_body.register
def _(block: SnakemakeDirectiveBlock, mode: Mode, state: FormatState) -> str:
    """Sort directives in the order of subautomata,
    and format them together with the head line.
    """
    formatted: list[str] = []
    directives: dict[str, str] = {}
    tail_noncoding: list[str] = []
    indent = TAB * (block.deindent_level + 1)
    order = state.module_order if isinstance(block, Module) else state.rule_order
    for index, sub in enumerate(block.body_blocks):
        # `# fmt: off[next]` only applies to the directive that follows it; a
        # pending directive from the previous iteration must not leak further.
        state = state.consume_skip_next()
        if tail_noncoding:
            raise UnsupportedSyntax("Unexpected comments before a directive body")
        if isinstance(sub, PythonBlock):
            formatted_docstring = format_block(sub, mode, state)
            for line in sub.head_linestrs:
                state = state.update(line.lstrip())
            if index + 1 < len(block.body_blocks):
                following = block.body_blocks[index + 1]
                if not isinstance(following, SnakemakeBlock):
                    token = following.start_token or block.start_token
                    raise UnsupportedSyntax(
                        f"{line_nb(token)}Unexpected block type in "
                        "snakemake keyword block"
                    )
                head_noncoding = following.colon_line.head_noncoding
                if head_noncoding and head_noncoding[0].type == tokenize.NL:
                    # A blank line the user wrote between the docstring
                    # and the first directive is kept
                    formatted_docstring += "\n"
            formatted.append(formatted_docstring)
            continue
        if not isinstance(sub, SnakemakeBlock):
            token = sub.start_token or block.start_token
            raise UnsupportedSyntax(
                f"{line_nb(token)}Unexpected block type in " "snakemake keyword block"
            )
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
            elif state.skip_next:
                # a blank line ends a `# fmt: off[next]` region
                state = state.consume_skip_next()
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
                if directives:
                    raise UnsupportedSyntax(
                        "Directives were already flushed once fmt: off[sort]"
                    )
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
    if directives:
        raise UnsupportedSyntax(f"Unknown directives: {', '.join(directives)}")


@format_head.register
def _(block: UseRule, mode: Mode):
    """Allow:
    use rule * from other_workflow exclude ruleC as other_*
    use rule * from other_workflow exclude ruleC
    use rule * from other_workflow as other_*
    use rule * from other_workflow
    use rule a,b from other_workflow
    """
    indent = TAB * block.deindent_level
    source_line = block.head_source_line()
    if FormatState.found_skip(source_line):
        return indent + source_line.lstrip(), ""
    head = indent + "use rule " + ",".join(block.whitelist)
    if block.module:
        head += " from " + block.module
        if block.exclude:
            head += " exclude " + ",".join(block.exclude)
    if block.rename:
        head += " as " + block.rename
    if block.body_blocks:
        head += " with:"
    comment_index = source_line.find("#")
    if comment_index >= 0:
        head_comment = black.format_python(
            source_line[comment_index:], mode, partial="#"
        )
    else:
        head_comment = "\n"
    return head, head_comment


@format_body.register
def _(block: Rule.Shell, mode: Mode, state: FormatState) -> str:
    """Format the body, then (if enabled) reformat its lone string
    literal as shell code with `shfmt`.

    Going through the normal body formatting first keeps surrounding
    comments/blank lines and the trailing-comma handling; only the
    literal itself is then swapped for its `shfmt`'ed form.
    """
    formatted = _format_arguments_body(block, mode, state)
    if not state.format_shell:
        return formatted
    tokens = TokenIterator("", tokenize.generate_tokens(splitlines(formatted).readline))
    while True:
        try:
            component = tokens.next_component()
        except UnsupportedSyntax:
            return formatted
        if not (
            len(component) == 1
            and component[0].type == tokenize.STRING
            or is_fstring_start(component[0])
        ):
            if any(effective(token) for token in component):
                return formatted
            # Comment, newline, indent or other non-coding token.
            continue
        if any(effective(token) for token in tokens.rest):
            return formatted

        start = _token_offset(formatted, component[0].start)
        end = _token_offset(formatted, component[-1].end)
        shell_formatted = format_python_string_literal(
            formatted[start:end], block.deindent_level + 1
        )
        return formatted[:start] + shell_formatted + formatted[end:]


def _token_offset(text: str, position: tuple[int, int]) -> int:
    """Character offset of a tokenize ``(line, column)`` position in ``text``."""
    line, column = position
    offset = 0
    for _ in range(line - 1):
        offset = text.find("\n", offset) + 1
    return offset + column


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
                splitlines(token.line),
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
    slices: list[tuple[Argument, str]] = []
    for param in block.params:
        if not param.tokens:
            continue
        end = param.tokens[-1].end
        slices.append((param, source(start, end)))
        start = end

    # The comment after the last parameter, only when not trailing_comma
    trailing_comment = ""
    parts: list[str] = []
    if trailing_comma or len(slices) > 1:
        # positional (unnamed) before keyword
        slices.sort(key=lambda param_text: param_text[0].is_keyword)
        for param, text in slices:
            if not param.has_comma:
                text += "\n,"
            parts.append(text)
    else:
        param_str = slices[0][1]
        if slices and block.params[0].tokens:
            value_end = block.params[0].tokens[-1].end
            for candidate in block.iter:
                if (
                    candidate.start[0] == value_end[0]
                    and candidate.type == tokenize.COMMENT
                ):
                    # start is from param in block.params
                    # which is either NL or effective (Argument._munch)
                    # if is NL, cut, else must before the comment.
                    cut = candidate.start[1] - start[1]
                    if cut < 0:
                        param_str = param_str[:cut]
                    start = candidate.end
                    trailing_comment = candidate.string
                    break
        parts.append(param_str.rstrip(","))
    parts.append(source(start, token.end))
    tail_noncoding = "".join(tokens2linestrs(iter(block.tail_noncoding)))
    formatable = "".join(parts) + tail_noncoding
    # Directives always keep one parameter per line, even when the user enables
    # Black's skip-magic-trailing-comma option.
    parameter_mode = replace(mode, magic_trailing_comma=True)
    formatted = black.format_python(
        formatable,
        parameter_mode,
        deindent_level,
        partial="(",
        start_token=first,
    )
    if trailing_comment:
        formatted = formatted.rstrip("\n") + "  " + trailing_comment + "\n"
    return formatted
