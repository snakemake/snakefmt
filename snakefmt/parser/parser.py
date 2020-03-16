import tokenize

from black import InvalidInput

from snakefmt.exceptions import InvalidPython
from snakefmt.parser.grammar import Grammar, SnakeGlobal, accept_python_code
from snakefmt.parser.syntax import (
    KeywordSyntax,
    Parameter,
    ParameterSyntax,
    TokenIterator,
    run_black_format_str,
)


class Snakefile:
    """
    Adapted from snakemake.parser.Snakefile
    """

    def __init__(self, fpath_or_stream, rulecount=0):
        try:
            self.stream = open(fpath_or_stream, encoding="utf-8")
        except TypeError:
            self.stream = fpath_or_stream

        self.tokens = tokenize.generate_tokens(self.stream.readline)
        self.rulecount = rulecount
        self.lines = 0

    def __next__(self):
        return next(self.tokens)

    def __iter__(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.stream.close()


class Parser:
    def __init__(self, snakefile: TokenIterator):
        self.indent = 0
        self.grammar = Grammar(
            SnakeGlobal(), KeywordSyntax("Global", self.indent, accepts_py=True)
        )
        self.context_stack = [self.grammar]

        self.snakefile = snakefile
        self.result = ""
        self.buffer = ""
        self.first = True

        status = self.context.get_next_queriable(self.snakefile)
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
                if not self.context.accepts_python_code:
                    raise SyntaxError(
                        f"L{status.token.start[0]}: Unrecognised keyword '{keyword}' "
                        f"in {self.context.keyword_name} definition"
                    )
                else:
                    self.buffer += keyword

            status = self.context.get_next_queriable(self.snakefile)
            self.buffer += status.buffer
        self.flush()

    @property
    def language(self):
        return self.grammar.language

    @property
    def context(self):
        return self.grammar.context

    def flush(self):
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

    def process_keyword(self, status):
        keyword = status.token.string
        accepts_py = True if keyword in accept_python_code else False
        new_grammar = self.language.get(keyword)
        if self.indent == 0 and not self.first:
            self.result += "\n\n"
        if self.first:
            self.first = False
        if issubclass(new_grammar.context, KeywordSyntax):
            self.indent += 1
            self.grammar = Grammar(
                new_grammar.language(),
                new_grammar.context(keyword, self.indent, self.snakefile, accepts_py),
            )
            # TODO: below is hacky, could do a general de-duplication based on keyword + name (eg rule)
            if self.context.accepts_python_code:
                self.context_stack[-1].context.add_processed_keyword(status.token)
            self.context_stack.append(self.grammar)
            self.process_keyword_context()
            return None

        elif issubclass(new_grammar.context, ParameterSyntax):
            param_context = new_grammar.context(
                keyword, self.indent + 1, self.snakefile
            )
            self.process_keyword_param(param_context)
            self.context.add_processed_keyword(status.token)
            return KeywordSyntax.Status(
                param_context.token,
                param_context.cur_indent,
                status.buffer,
                param_context.eof,
            )

    def context_exit(self, status):
        while self.indent > status.indent:
            callback_grammar = self.context_stack.pop()
            if callback_grammar.context.accepts_python_code:
                self.flush()
            else:
                callback_grammar.context.check_empty()
            self.indent -= 1
            self.grammar = self.context_stack[-1]
        assert len(self.context_stack) == self.indent + 1

    def get_formatted(self):
        return self.result


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
    used_indent = "\t" * (parameters.target_indent - 1)
    result = f"{used_indent}{parameters.keyword_name}: \n"
    param_indent = used_indent + "\t"
    for elem in parameters.positional_params:
        result += format_param(elem, param_indent, single_param)
    for elem in parameters.keyword_params:
        result += format_param(elem, param_indent, single_param)
    return result
