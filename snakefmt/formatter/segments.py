import tokenize
from typing import Iterable

from snakefmt.config import Mode
from snakefmt.formatter import black
from snakefmt.formatter.blocks import format_block
from snakefmt.formatter.state import FormatState
from snakefmt.parser.blocks import Block, ColonBlock, SnakemakeBlock
from snakefmt.parser.tokens import TAB, deindent_lines, tokens2linestrs


def format_segments(
    block: Block, mode: Mode, state: FormatState
) -> Iterable[tuple[str, str | None]]:
    """yield:
    - [unformated_python_code, None]
    - [formated_snakemake_code, indent_str]

    `SnakemakeInlineArgumentBlock` should be taken very careful of,
    since they are formatedd as `def` blocks, and may not sperate from
    blocks with different keywords. So here are the special principles
    specially for one-line snakemake blocks:

    - the previous block should be in the same indent of current block;
    - if previous line (with no newline nor comments) is:
            1, `def` block; or
            2. another one-line block with differnt keyword:
        then add a newline
    - if previous line is the same keyword with:
            only comment lines but NO blank line between:
        merge the two lines into one block, with comments in between
    - (doesn't matter if this block is actually one-line or not)
    """
    # comment fmt directives in head_linestrs
    #  will effect on post blocks of the same indent,
    # so should be updated during the parent body_blocks iteration.
    for line in block.head_linestrs:
        yield line, None
    last_keyword = ""
    line = ""
    state = state.reset_sort()
    for sub in block.body_blocks:
        restart_state = state = state.consume_skip_next()
        # update state from head_noncoding
        for head_line in sub.head_lines:
            for noncoding_token in head_line.head_noncoding:
                if noncoding_token.type == tokenize.COMMENT:
                    state = state.update(noncoding_token.string)
                elif state.skip_next and not noncoding_token.line.strip():
                    state = state.consume_skip_next()
        if isinstance(sub, ColonBlock):
            if sub.keyword == "def":
                if last_keyword and last_keyword != "def":
                    # Oh, differnt keyword detected, so (last)line must exists
                    # Then check if that line is start
                    if (
                        line.rstrip()
                        .rsplit("\n", 1)[-1]
                        .startswith(sub.indent_str + last_keyword)
                    ):
                        # If NO any line before the first line of this block,
                        # black cannot split them: Add one to force splitting
                        if not sub.head_lines[0].head_noncoding:
                            yield "\n", None
                last_keyword = "def"
                for line, indent in format_segments(sub, mode, state):
                    # record `line` for next useage
                    yield line, indent
            elif isinstance(sub, SnakemakeBlock):
                for line, indent in format_snakemake_segments(
                    sub, mode, restart_state, last_keyword
                ):
                    yield line, indent
                last_keyword = sub.keyword
            else:
                last_keyword = ""
                yield from format_segments(sub, mode, state)
        else:
            last_keyword = ""
            yield from format_segments(sub, mode, state)
    if block.tail_noncoding:
        yield "".join(tokens2linestrs(iter(block.tail_noncoding))), None


def format_snakemake_segments(
    block: SnakemakeBlock, mode: Mode, state: FormatState, last_keyword=""
) -> Iterable[tuple[str, str | None]]:
    """yield:
    - [unformated_python_code, None]
    - [formated_snakemake_code, indent]

    If state.skip_next is True, or state.fmt_on is False,
    return unformatted content with proper True/False markers.
    """

    # Get noncoding_lines early to check fmt directives
    indent_str = TAB * block.deindent_level
    assert len(block.head_lines) == 1, "Snakemake keywords should only in one line"
    noncoding_lines: list[str] = []
    last_fmt_on = state.fmt_on
    # Check if there's fmt: on/off in noncoding_lines to update state
    for noncoding_line in tokens2linestrs(iter(block.colon_line.head_noncoding)):
        if not noncoding_line.strip():
            last_keyword = ""
        else:
            state = state.update(noncoding_line.lstrip())
        if state.not_format:
            noncoding_lines.append(noncoding_line)
        else:
            noncoding_lines.append(
                indent_str + black.format_python(noncoding_line, mode, 0)
            )
    if last_fmt_on and state.fmt_on:
        if last_keyword == block.keyword:
            # pre-format these lines and yield together
            pre_formatted = black.format_python(
                "".join(noncoding_lines), mode, 0
            ).splitlines(keepends=True)
            for line in pre_formatted:
                if state.found_skip(line):
                    yield line, None
                else:
                    yield indent_str + line.lstrip(), block.indent_str
        else:
            if not noncoding_lines:
                yield "\n", None
            yield "".join(noncoding_lines), None
    else:
        yield "".join(noncoding_lines), None

    # Check if this block should be skipped from formatting
    if state.not_format:
        raw = "".join(
            deindent_lines(
                block.indent_str,
                block.deindent_level,
                block.raw_source_linestrs(),
            )
        )
        # Trailing blank lines from body_blocks belong to the next block's
        # separator, not this block's content. Strip extra trailing blank
        # lines so the compilation loop doesn't double-count them with
        # black's blank-line insertion.
        if raw.endswith("\n\n") and state.skip_next:
            n_trailing_space = len(raw) - len(raw.rstrip("\n")) - 1
            raw = raw.rstrip("\n") + "\n"
        else:
            n_trailing_space = 0
        yield raw, block.indent_str
        if n_trailing_space > 0:
            yield "\n" * n_trailing_space, None
    else:
        yield format_block(block, mode, state), block.indent_str
    if block.tail_noncoding:
        yield "".join(tokens2linestrs(iter(block.tail_noncoding))), None
