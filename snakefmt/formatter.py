import textwrap
from typing import Type

from black import format_str as black_format_str, FileMode, InvalidInput

from snakefmt import DEFAULT_LINE_LENGTH
from snakefmt.exceptions import InvalidPython, InvalidParameterSyntax
from snakefmt.parser.parser import Parser
from snakefmt.parser.syntax import (
    Parameter,
    ParameterSyntax,
    SingleParam,
    TAB,
)
from snakefmt.types import TokenIterator

rule_like_formatted = {"rule", "checkpoint"}


class Formatter(Parser):
    def __init__(
        self, snakefile: TokenIterator, line_length: int = DEFAULT_LINE_LENGTH
    ):
        self._line_length = line_length
        self.result = ""
        self.from_rule = False
        self.first = True
        super().__init__(snakefile)  # Call to parse snakefile

    def get_formatted(self):
        return self.result

    def flush_buffer(self):
        if len(self.buffer) == 0 or self.buffer.isspace():
            self.buffer = ""
            return
        formatted = self.run_black_format_str(
            self.buffer, self.target_indent, InvalidPython
        )
        self.from_comment = True if formatted.split("\n")[-1][0] == "#" else False
        self.add_newlines(self.target_indent, keyword_name="")
        self.result += formatted + "\n"
        self.buffer = ""

    def process_keyword_context(self):
        context = self.grammar.context
        self.add_newlines(context.target_indent - 1, context.keyword_name)
        formatted = TAB * (context.target_indent - 1)
        formatted = f"{formatted}{context.keyword_name}:{context.comment}" + "\n"
        self.result += formatted

    def process_keyword_param(self, param_context):
        self.add_newlines(param_context.target_indent - 1, param_context.keyword_name)
        self.result += self.format_params(param_context)

    def run_black_format_str(
        self, string: str, target_indent: int, exception: Type[Exception]
    ) -> str:
        try:
            fmted = black_format_str(
                string, mode=FileMode(line_length=self._line_length)
            )[:-1]
        except InvalidInput as err:
            if exception == InvalidPython:
                msg = "python code"
            elif exception == InvalidParameterSyntax:
                msg = "a parameter value"
            else:
                msg = str(err)
            raise exception(
                f"The following was treated as {msg} to format with black:"
                f"\n```\n{string}\n```\n"
                "And was not recognised as valid.\n"
                "Did you use the right indentation?"
            ) from None
        indented = textwrap.indent(fmted, TAB * target_indent)
        return indented

    def format_param(
        self, parameter: Parameter, used_indent: str, single_param: bool = False
    ):
        comments = "\n{i}".format(i=used_indent).join(parameter.comments)
        val = parameter.value
        if parameter.is_string:
            val = val.replace('"""', '"')
            val = val.replace("\n", "").replace(TAB, "")
            if used_indent != "":
                val = val.replace('""', '"\n"')
        val = self.run_black_format_str(val, 0, InvalidParameterSyntax)
        val = val.replace("\n", f"\n{used_indent}")

        if single_param:
            result = f"{val}{comments}\n"
        else:
            result = f"{val},{comments}\n"
        if parameter.has_key():
            result = f"{parameter.key}={result}"
        result = f"{used_indent}{result}"
        return result

    def format_params(self, parameters: ParameterSyntax) -> str:
        single_param = False
        used_indent = TAB * (parameters.target_indent - 1)
        result = f"{used_indent}{parameters.keyword_name}:{parameters.comment}"

        is_shell = parameters.keyword_name == "shell"

        if issubclass(parameters.__class__, SingleParam) and not is_shell:
            single_param = True
            result += " "
            used_indent = ""
        else:
            result += "\n"
            used_indent += TAB
        if is_shell:
            single_param = True

        for elem in parameters.positional_params:
            result += self.format_param(elem, used_indent, single_param)
        for elem in parameters.keyword_params:
            result += self.format_param(elem, used_indent, single_param)
        return result

    def add_newlines(self, cur_indent: int, keyword_name: str = ""):
        is_rule_like = (
            keyword_name is not "" and keyword_name.split()[0] in rule_like_formatted
        )
        if cur_indent == 0:
            if self.from_rule:
                self.result += "\n\n"
            elif not self.first:
                if is_rule_like and not self.from_comment:
                    self.result += "\n\n"
                elif keyword_name == "":
                    self.result += "\n"  # Add newline for python code
            self.from_rule = True if is_rule_like else False
        if self.first:
            self.first = False
