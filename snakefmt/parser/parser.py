from snakemake import parser as orig_parser
from black import format_str as black_format_str, FileMode
import tokenize
from abc import ABC, abstractmethod

from .grammar import Grammar, SnakeGlobal
from .syntax import TokenIterator, KeywordSyntax, ParameterSyntax, Parameter


def getUntil(snakefile: TokenIterator, type) -> str:
    result = ""
    while True:
        token = next(snakefile)
        if token.type == tokenize.NAME:
            result += " "
        result += token.string
        if token.type == type or token.type == tokenize.ENDMARKER:
            break
    return result


class Parser(ABC):
    def __init__(self, snakefile_path: str):
        self.indent = 0
        self.grammar = Grammar(SnakeGlobal(), KeywordSyntax("Global", self.indent))
        self.context_stack = [self.grammar]

        self.snakefile = orig_parser.Snakefile(snakefile_path)
        self.result = ""
        self.buffer = ""

        status = self.context.get_next_keyword(self.snakefile)
        self.buffer += status.buffer

        while True:
            if status.indent < self.indent:
                self.context_exit(status)

            if status.eof:
                break

            keyword = status.token.string
            if self.language.recognises(keyword):
                self.flush()
                new_status = self.process_keyword(status)
                if new_status is not None:
                    status = new_status
                    continue
            else:
                if self.indent != 0:
                    raise SyntaxError(
                        f"L{status.token.start[0]}: Unrecognised keyword '{keyword}' "
                        f"in {self.context.keyword_name} definition"
                    )
                else:
                    self.buffer += keyword
                    self.buffer += getUntil(self.snakefile, tokenize.NEWLINE)

            status = self.context.get_next_keyword(self.snakefile)
            self.buffer += status.buffer
        self.flush()

    @property
    def language(self):
        return self.grammar.language

    @property
    def context(self):
        return self.grammar.context

    @abstractmethod
    def flush(self):
        pass

    @abstractmethod
    def process_keyword_context(self):
        pass

    @abstractmethod
    def process_keyword_param(self, param_context):
        pass

    def process_keyword(self, status):
        keyword = status.token.string
        new_grammar = self.language.get(keyword)
        if issubclass(new_grammar.context, KeywordSyntax):
            self.indent += 1
            self.grammar = Grammar(
                new_grammar.language(),
                new_grammar.context(keyword, self.indent, self.snakefile),
            )
            self.context_stack.append(self.grammar)
            self.process_keyword_context()
            return None

        elif issubclass(new_grammar.context, ParameterSyntax):
            param_context = new_grammar.context(keyword, self.indent, self.snakefile)
            self.context.add_processed_keyword(status.token)
            self.process_keyword_param(param_context)
            return KeywordSyntax.Status(
                param_context.token,
                param_context.cur_indent,
                status.buffer,
                param_context.eof,
            )

    def context_exit(self, status):
        while self.indent > status.indent:
            callback_grammar = self.context_stack.pop()
            callback_grammar.context.check_empty()
            self.indent -= 1
            self.grammar = self.context_stack[-1]
        assert len(self.context_stack) == self.indent + 1


class Formatter(Parser):
    def __init__(self, snakefile_path: str):
        super().__init__(snakefile_path)

    def get_formatted(self):
        return self.result

    def flush(self):
        if len(self.buffer) > 0:
            self.result += black_format_str(self.buffer, mode=FileMode())
            self.buffer = ""
        if self.indent == 0:
            self.result += "\n"

    def process_keyword_context(self):
        self.result += self.grammar.context.line

    def process_keyword_param(self, param_context):
        self.result += format_params(param_context)


def format_param(parameter: Parameter, used_indent: str, single_param: bool = False):
    comments = "\n{i}".format(i=used_indent).join(parameter.comments)
    if single_param:
        result = f"{parameter.value} {comments}\n"
    else:
        result = f"{parameter.value}, {comments}\n"
    if parameter.has_key():
        result = f"{parameter.key} = {result}"
    result = f"{used_indent}{result}"
    return result


def format_params(parameters: ParameterSyntax) -> str:
    single_param = False
    if parameters.num_params() == 1:
        single_param = True
    used_indent = "\t" * parameters.indent
    result = f"{used_indent}{parameters.keyword_name}: \n"
    param_indent = used_indent + "\t"
    for elem in parameters.positional_params:
        result += format_param(elem, param_indent, single_param)
    for elem in parameters.keyword_params:
        result += format_param(elem, param_indent, single_param)
    return result
