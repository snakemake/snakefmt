import textwrap
from typing import Type

from black import format_str as black_format_str, FileMode, InvalidInput

from snakefmt import DEFAULT_LINE_LENGTH
from snakefmt.exceptions import InvalidPython, InvalidParameterSyntax
from snakefmt.parser.parser import Parser
from snakefmt.parser.syntax import Parameter, ParameterSyntax
from snakefmt.parser.grammar import SnakeRule
from snakefmt.types import TokenIterator


class Formatter(Parser):
    def __init__(
        self, snakefile: TokenIterator, line_length: int = DEFAULT_LINE_LENGTH
    ):
        self._line_length = line_length
        super().__init__(snakefile)  # Call to parse snakefile

    def get_formatted(self):
        return self.result

    def flush_buffer(self):
        if len(self.buffer) == 0 or self.buffer.isspace():
            self.buffer = ""
            return
        self.buffer = self.buffer.replace("\t", "")
        formatted = (
            self.run_black_format_str(self.buffer, self.indent, InvalidPython) + "\n"
        )
        if self.indent == 0 and not self.first:
            formatted = "\n" + formatted
        if self.first:
            self.first = False
        self.result += formatted
        self.buffer = ""

    def process_keyword_context(self):
        context = self.grammar.context
        formatted = "\t" * (context.target_indent - 1)
        formatted = f"{formatted}{context.keyword_name}:{context.comment}" + "\n"
        self.result += formatted

    def process_keyword_param(self, param_context):
        self.result += self.format_params(param_context)

    def run_black_format_str(
        self, string: str, indent: int, exception: Type[Exception]
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
        indented = textwrap.indent(fmted, "\t" * indent)
        return indented

    def format_param(
        self, parameter: Parameter, used_indent: str, single_param: bool = False
    ):
        comments = "\n{i}".format(i=used_indent).join(parameter.comments)
        val = parameter.value
        if parameter.is_string:
            val = val.replace('"""', '"')
            val = val.replace("\n", "").replace("\t", "")
            val = val.replace('""', '"\n"')
        val = self.run_black_format_str(val, 0, InvalidParameterSyntax)
        val = val.replace("\n", f"\n{used_indent}")

        within_rule = isinstance(self.grammar.language, SnakeRule)
        if single_param and not within_rule:
            result = f"{val} {comments}\n"
        else:
            result = f"{val}, {comments}\n"
        if parameter.has_key():
            result = f"{parameter.key} = {result}"
        result = f"{used_indent}{result}"
        return result

    def format_params(self, parameters: ParameterSyntax) -> str:
        single_param = False
        if parameters.num_params() == 1:
            single_param = True

        used_indent = "\t" * (parameters.target_indent - 1)
        result = f"{used_indent}{parameters.keyword_name}: \n"
        param_indent = used_indent + "\t"

        for elem in parameters.positional_params:
            result += self.format_param(elem, param_indent, single_param)
        for elem in parameters.keyword_params:
            result += self.format_param(elem, param_indent, single_param)
        return result
