import logging

PEP8_BLOCK_COMMENTS = """PEP8 recommends block comments appear before what they describe
(see https://www.python.org/dev/peps/pep-0008/#id30)"""


def block_comment_below(keyword: str, line_nb: int):
    msg = f'Keyword "{keyword}" at line {line_nb} has comments under a value.'
    logging.warning(f"{msg}\n{PEP8_BLOCK_COMMENTS}")


def comment_relocation(keyword: str, line_nb: int):
    msg = (
        f'Inline-formatted keyword "{keyword}" at line {line_nb} had its'
        " comments relocated above it."
    )
    logging.warning(f"{msg}\n{PEP8_BLOCK_COMMENTS}")
