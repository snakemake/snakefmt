import logging
from typing import Optional


class LogConfig:
    log_template = "[%(levelname)s]{0} %(message)s"

    @classmethod
    def init(cls, log_level: int):
        cls.logger = logging.getLogger("snakefmt")
        cls.handler = logging.StreamHandler()
        cls.logger.addHandler(cls.handler)
        cls.handler.setFormatter(logging.Formatter(cls.log_template.format("")))
        cls.logger.setLevel(log_level)

    @classmethod
    def get_logger(cls):
        return cls.logger

    @classmethod
    def switch(cls, path: Optional[str] = None) -> None:
        if path is None:
            cls.handler.setFormatter(logging.Formatter(cls.log_template.format("")))
        else:
            cls.handler.setFormatter(
                logging.Formatter(cls.log_template.format(f' In file "{path}": '))
            )


PEP8_BLOCK_COMMENTS = """PEP8 recommends block comments appear before what they describe
(see https://www.python.org/dev/peps/pep-0008/#id30)"""


class Warnings:
    @staticmethod
    def block_comment_below(keyword: str, line_nb: int):
        msg = f'Keyword "{keyword}" at line {line_nb} has comments under a value.'
        LogConfig.get_logger().warning(f"{msg}\n\t{PEP8_BLOCK_COMMENTS}")

    @staticmethod
    def comment_relocation(keyword: str, line_nb: int):
        msg = (
            f'Inline-formatted keyword "{keyword}" at line {line_nb} had its'
            " comments relocated above it."
        )
        LogConfig.get_logger().warning(f"{msg}\n{PEP8_BLOCK_COMMENTS}")
