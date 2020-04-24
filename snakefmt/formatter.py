import re
import textwrap
from ast import parse as ast_parse
from pathlib import Path
from typing import Optional, Union

import black
import toml

from snakefmt import DEFAULT_LINE_LENGTH
from snakefmt.exceptions import (
    InvalidPython,
    InvalidParameterSyntax,
    InvalidBlackConfiguration,
    MalformattedToml,
)
from snakefmt.parser.grammar import SnakeRule
from snakefmt.parser.parser import Parser
from snakefmt.parser.syntax import (
    Parameter,
    ParameterSyntax,
    SingleParam,
    RuleInlineSingleParam,
    TAB,
)
from snakefmt.types import TokenIterator

PathLike = Union[Path, str]
rule_like_formatted = {"rule", "checkpoint"}

triple_quote_matcher = re.compile(r"(\"{3}.*?\"{3})|('{3}.*?'{3})", re.DOTALL)


class Formatter(Parser):
    def __init__(
        self,
        snakefile: TokenIterator,
        line_length: int = DEFAULT_LINE_LENGTH,
        black_config: Optional[PathLike] = None,
    ):
        self._line_length = line_length
        self.result = ""
        self.from_rule, self.from_comment = False, False
        self.first = True

        if black_config is None:
            self.black_mode = black.FileMode(line_length=self.line_length)
        else:
            self.black_mode = self.read_black_config(black_config)

        super().__init__(snakefile)  # Call to parse snakefile

    def read_black_config(self, path: PathLike) -> black.FileMode:
        if not Path(path).is_file():
            raise FileNotFoundError(f"{path} is not a file.")

        try:
            pyproject_toml = toml.load(path)
            config = pyproject_toml.get("tool", {}).get("black", {})
        except toml.TomlDecodeError as error:
            raise MalformattedToml(error)

        if "line_length" not in config:
            config["line_length"] = self.line_length

        try:
            return black.FileMode(**config)
        except TypeError as error:
            raise InvalidBlackConfiguration(error)

    @property
    def line_length(self) -> int:
        return self._line_length

    def get_formatted(self):
        return self.result

    def flush_buffer(self, from_python: bool = False):
        if len(self.buffer) == 0 or self.buffer.isspace():
            self.result += self.buffer
            self.buffer = ""
            return

        if not from_python:
            formatted = self.run_black_format_str(self.buffer, self.target_indent)
            self.from_comment = True if formatted.splitlines()[-1][0] == "#" else False
            self.add_newlines(self.target_indent, keyword_name="")
        else:
            formatted = self.buffer.rstrip(TAB)
        self.result += formatted
        self.buffer = ""

    def process_keyword_context(self):
        cur_indent = self.context.cur_indent
        self.add_newlines(cur_indent, self.context.keyword_name)
        formatted = (
            f"{TAB * cur_indent}{self.context.keyword_name}:{self.context.comment}"
            + "\n"
        )
        self.result += formatted

    def process_keyword_param(self, param_context):
        self.add_newlines(param_context.target_indent - 1, param_context.keyword_name)
        in_rule = issubclass(param_context.incident_vocab.__class__, SnakeRule)
        self.result += self.format_params(param_context, in_rule)

    def run_black_format_str(self, string: str, target_indent: int) -> str:
        try:
            fmted = black.format_str(string, mode=self.black_mode)
        except black.InvalidInput as e:
            raise InvalidPython(
                f"Got error:\n```\n{str(e)}\n```\n" f"while formatting code with black."
            ) from None

        # Only indent non-triple-quoted string portions
        pos = 0
        used_indent = TAB * target_indent
        indented = ""
        for match in re.finditer(triple_quote_matcher, fmted):
            indented += textwrap.indent(fmted[pos : match.start()], used_indent)
            match_slice = fmted[match.start() : match.end()]
            indented += f"{used_indent}{match_slice}"
            pos = match.end()
        indented += textwrap.indent(fmted[pos:], used_indent)

        return indented

    def format_param(
        self,
        parameter: Parameter,
        target_indent: str,
        inline_formatting: bool,
        single_param: bool = False,
    ) -> str:
        if inline_formatting:
            target_indent = 0
        comments = f"\n{TAB * target_indent}".join(parameter.comments)
        val = str(parameter)

        try:
            ast_parse(f"param({val})")
        except SyntaxError:
            raise InvalidParameterSyntax(f"{parameter.line_nb}{val}") from None

        if inline_formatting:
            val = val.replace("\n", "")
        try:
            val = self.run_black_format_str(val, target_indent)
            if parameter.has_a_key():  # Remove space either side of '='
                match_equal = re.match("(.*?) = (.*)", val, re.DOTALL)
                val = f"{match_equal.group(1)}={match_equal.group(2)}"

        except InvalidPython:
            if "**" in val:
                val = val.replace("** ", "**")
            pass

        val = val.strip("\n")
        if single_param:
            result = f"{val}{comments}\n"
        else:
            result = f"{val},{comments}\n"
        return result

    def format_params(self, parameters: ParameterSyntax, in_rule: bool) -> str:
        target_indent = parameters.target_indent
        used_indent = TAB * (target_indent - 1)
        result = f"{used_indent}{parameters.keyword_name}:{parameters.comment}"

        p_class = parameters.__class__
        single_param = issubclass(p_class, SingleParam)
        inline_fmting = single_param
        # Cancel single param formatting if in rule-like context and param not inline
        if in_rule and p_class is not RuleInlineSingleParam:
            inline_fmting = False

        if inline_fmting:
            result += " "
        else:
            result += "\n"

        for elem in parameters.all_params:
            result += self.format_param(
                elem, target_indent, inline_fmting, single_param
            )
        return result

    def add_newlines(self, cur_indent: int, keyword_name: str = ""):
        if cur_indent == 0:
            if self.from_rule:
                self.result += "\n\n"
            elif not self.first:
                if self.rule_like(keyword_name) and not self.from_comment:
                    self.result += "\n\n"
                elif keyword_name == "":
                    self.result += "\n"  # Add newline for python code
            self.from_rule = True if self.rule_like(keyword_name) else False
        if self.first:
            self.first = False

    def rule_like(self, kwrd):
        return kwrd != "" and kwrd.split()[0] in rule_like_formatted
