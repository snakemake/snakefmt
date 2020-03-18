import textwrap
from black import format_str as black_format_str, FileMode, InvalidInput
from snakefmt import DEFAULT_LINE_LENGTH

from snakefmt.parser.parser import Parser
from snakefmt.exceptions import InvalidPython
from snakefmt.types import TokenIterator

from snakefmt.parser.syntax import Parameter, ParameterSyntax


class Formatter(Parser):
    def __init__(
        self, snakefile: TokenIterator, line_length: int = DEFAULT_LINE_LENGTH
    ):
        self._line_length = line_length
        super().__init__(snakefile)

    def get_formatted(self):
        return self.result

    def flush_buffer(self):
        if len(self.buffer) == 0 or self.buffer.isspace():
            self.buffer = ""
            return
        try:
            self.buffer = self.buffer.replace("\t", "")
            formatted = run_black_format_str(self.buffer, self.indent) + "\n"
            if self.indent == 0:
                formatted = "\n" + formatted
            self.result += formatted
        except InvalidInput:
            raise InvalidPython(
                "The following was treated as python code to format with black:"
                f"\n```\n{self.buffer}\n```\n"
                "And was not recognised as valid python.\n"
                "Did you use the right indentation?"
            ) from None
        self.buffer = ""

    def process_keyword_context(self):
        self.result += self.grammar.context.line

    def process_keyword_param(self, param_context):
        self.result += format_params(param_context)


def format_param(parameter: Parameter, used_indent: str, single_param: bool = False):
    comments = "\n{i}".format(i=used_indent).join(parameter.comments)
    val = parameter.value
    if parameter.is_string:
        val = val.replace('"""', '"')
        val = val.replace("\n", "").replace("\t", "")
        val = val.replace('""', '"\n"')
    val = run_black_format_str(val, 0)
    val = val.replace("\n", f"\n{used_indent}")

    if single_param:
        result = f"{val} {comments}\n"
    else:
        result = f"{val}, {comments}\n"
    if parameter.has_key():
        result = f"{parameter.key} = {result}"
    result = f"{used_indent}{result}"
    return result


def format_params(parameters: ParameterSyntax) -> str:
    single_param = False
    if parameters.num_params() == 1:
        single_param = True

    used_indent = "\t" * (parameters.target_indent - 1)
    result = f"{used_indent}{parameters.keyword_name}: \n"
    param_indent = used_indent + "\t"

    for elem in parameters.positional_params:
        result += format_param(elem, param_indent, single_param)
    for elem in parameters.keyword_params:
        result += format_param(elem, param_indent, single_param)
    return result


def run_black_format_str(string: str, indent: int) -> str:
    fmted = black_format_str(string, mode=FileMode())[:-1]
    indented = textwrap.indent(fmted, "\t" * indent)
    return indented
