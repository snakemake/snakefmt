import textwrap
from typing import Type

from black import format_str as black_format_str, FileMode, InvalidInput

from snakefmt import DEFAULT_LINE_LENGTH
from snakefmt.exceptions import InvalidPython, InvalidParameterSyntax
from snakefmt.parser.parser import Parser
from snakefmt.parser.grammar import SnakeRule
from snakefmt.parser.syntax import (
    Syntax,
    Parameter,
    ParameterSyntax,
    SingleParam,
    SingleNumericParam,
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

    def flush_buffer(self, status: Syntax.Status = None):
        if len(self.buffer) == 0 or self.buffer.isspace():
            self.buffer = ""
            return

        add_pass = (
            True if status is not None and status.indent > self.target_indent else False
        )

        formatted = self.run_black_format_str(
            self.buffer, self.target_indent, InvalidPython, add_pass
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
        in_rule = issubclass(param_context.incident_vocab.__class__, SnakeRule)
        self.result += self.format_params(param_context, in_rule)

    def run_black_format_str(
        self,
        string: str,
        target_indent: int,
        exception: Type[Exception],
        add_pass: bool = False,
    ) -> str:
        if add_pass:
            pattern = f"{TAB * (target_indent + 1)}pass"
            string += pattern
        try:
            fmted = black_format_str(
                string, mode=FileMode(line_length=self._line_length)
            )
        except InvalidInput:
            if exception == InvalidPython:
                msg = "python code"
            elif exception == InvalidParameterSyntax:
                msg = "a parameter value"
            else:
                msg = "code"
            raise exception(
                f"The following was treated as {msg} to format with black:"
                f"\n```\n{string}\n```\n"
                "And was not recognised as valid.\n"
                "Did you use the right indentation?"
            ) from None

        indented = textwrap.indent(fmted, TAB * target_indent)
        if add_pass:
            indented = indented[: indented.rindex(pattern)]
        assert indented[-1] == "\n"  # black should add this
        return indented[:-1]

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

    def format_params(self, parameters: ParameterSyntax, in_rule: bool) -> str:
        used_indent = TAB * (parameters.target_indent - 1)
        result = f"{used_indent}{parameters.keyword_name}:{parameters.comment}"

        p_class = parameters.__class__
        single_param = issubclass(p_class, SingleParam)
        # single parameter formatting cancelled if we are in rule-like context and param is not numeric
        single_param_fmting = single_param
        if in_rule and p_class is not SingleNumericParam:
            single_param_fmting = False

        if single_param_fmting:
            result += " "
            used_indent = ""
        else:
            result += "\n"
            used_indent += TAB

        for elem in parameters.positional_params:
            result += self.format_param(elem, used_indent, single_param)
        for elem in parameters.keyword_params:
            result += self.format_param(elem, used_indent, single_param)
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
        return kwrd is not "" and kwrd.split()[0] in rule_like_formatted
