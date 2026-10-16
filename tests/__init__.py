import logging

from snakefmt.logging import LogConfig
from snakefmt.parser.global_block import setup_formatter as _setup_formatter


def setup_formatter(
    snake: str,
    line_length: int | None = None,
    sort_directives: bool = False,
    black_config_file=None,
    format_shell: bool = False,
    directive_order: tuple[str, ...] = (),
    module_directive_order: tuple[str, ...] = (),
):

    LogConfig.init(logging.DEBUG)

    return _setup_formatter(
        snake,
        line_length=line_length,
        sort_directives=sort_directives,
        black_config_file=black_config_file,
        format_shell=format_shell,
        directive_order=directive_order,
        module_directive_order=module_directive_order,
    )
