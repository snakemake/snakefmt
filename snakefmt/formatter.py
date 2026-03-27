import re
import textwrap
import tokenize
from ast import parse as ast_parse
from copy import copy
from typing import Optional

import black.parsing

from snakefmt.config import PathLike, read_black_config
from snakefmt.exceptions import InvalidParameterSyntax, InvalidPython
from snakefmt.logging import Warnings
from snakefmt.parser.parser import Parser, Snakefile, comment_start
from snakefmt.parser.syntax import (
    COMMENT_SPACING,
    InlineSingleParam,
    Parameter,
    ParameterSyntax,
    ParamList,
    SingleParam,
    Syntax,
    split_code_string,
)
from snakefmt.types import TAB

TAB_SIZE = len(TAB)
# this regex matches any docstring; can span multiple lines
docstring_matcher = re.compile(
    r"\s*([rR]?[\"']{3}.*?[\"']{3})", re.DOTALL | re.MULTILINE
)
contextual_matcher = re.compile(
    r"(.*?)^(if|elif|else|with|for|while)([^:]*)(:.*)", re.S | re.M
)
after_if_keywords = ("elif", "else")


def is_all_comments(string):
    return all(
        map(
            comment_start,
            [s for s in string.splitlines(keepends=True) if s.strip(" \t")],
        )
    )


def index_of_first_docstring(s: str) -> Optional[int]:
    """
    Returns the index (i.e., index of last quote character) of the first docstring in
    a string, or None if there are no docstrings.
    """
    match = docstring_matcher.search(s)
    if match is None:
        return None
    return match.end(1) - 1


class Formatter(Parser):
    def __init__(
        self,
        snakefile: Snakefile,
        line_length: Optional[int] = None,
        sort_directives: bool = False,
        black_config_file: Optional[PathLike] = None,
    ):
        self.result: str = ""
        self.lagging_comments: str = ""
        self.no_formatting_yet: bool = True
        self.fmt_sort_off = None if sort_directives else -1
        self.previous_result: str = ""
        self.keyword_spec: list[str] = []
        self.keywords: dict[str, str] = {}  # cache to sort

        self.black_mode = read_black_config(black_config_file)

        if line_length is not None:
            self.black_mode.line_length = line_length

        super().__init__(snakefile)  # Call to parse snakefile

    def get_formatted(self) -> str:
        return self.result

    @property
    def current_line_nb(self) -> int:
        """Report the line number of the rule defination"""
        return (self.previous_result + self.result).count("\n")

    def flush_buffer(
        self,
        from_python: bool = False,
        final_flush: bool = False,
        in_global_context: bool = False,
        exiting_keywords: bool = False,
    ) -> None:
        if len(self.buffer) == 0 or self.buffer.isspace():
            self.result += self.buffer
            self.buffer = ""
            if exiting_keywords and self.no_formatting_yet and self.result.rstrip("\n"):
                self.no_formatting_yet = False
            return

        if not from_python:
            formatted = self.run_black_format_str(self.buffer, self.block_indent)
            if self.keyword_indent > 0:
                formatted = self.align_strings(formatted, self.keyword_indent)
        else:
            # Invalid python syntax, eg lone 'else:' between two rules, can occur.
            # Below constructs valid code statements and formats them.
            if self.fmt_off_expected_index:
                self.buffer += self.fmt_off_expected_index
                self.fmt_off_expected_index = ""
            re_match = contextual_matcher.match(self.buffer)
            if re_match is not None:
                callback_keyword = re_match.group(2)
                used_keyword = (
                    "if" if callback_keyword in after_if_keywords else callback_keyword
                )
                condition = re_match.group(3)
                if condition != "":
                    test_substitute = f"{used_keyword}{condition}"
                else:
                    test_substitute = f"{used_keyword} a"
                to_format = (
                    f"{re_match.group(1)}{test_substitute}" f"{re_match.group(4)}pass"
                )
                formatted = self.run_black_format_str(to_format, self.block_indent)
                re_rematch = contextual_matcher.match(formatted)
                assert re_rematch, (
                    "This should always match as we just formatted it with the same "
                    "regex. If this error is raised, it's a bug in snakefmt's "
                    "handling of snakemake syntax. Please report this to the "
                    "developers with the code so we can fix it: "
                    "https://github.com/snakemake/snakefmt/issues"
                )
                if condition != "":
                    callback_keyword += re_rematch.group(3)
                formatted = (
                    f"{re_rematch.group(1)}{callback_keyword}" f"{re_rematch.group(4)}"
                )
                formatted_lines = formatted.splitlines(keepends=True)
                formatted = "".join(formatted_lines[:-1])  # Remove the 'pass' line
            else:
                formatted = self.run_black_format_str(self.buffer, self.block_indent)

            if self.syntax is not None:
                formatted = textwrap.indent(formatted, f"{TAB * self.block_indent}")

        # Re-add newline removed by black for proper parsing of comments
        if self.buffer.endswith("\n\n"):
            if comment_start(self.buffer.rstrip().splitlines()[-1]):
                formatted += "\n"
        # Only stick together separated single-parm keywords when separated by comments
        if not is_all_comments(self.buffer):
            self.last_recognised_keyword = ""
        self.add_newlines(self.block_indent, formatted, final_flush, in_global_context)
        self.buffer = ""

    def process_keyword_context(self, in_global_context: bool):
        cur_indent = self.syntax.cur_indent
        self.add_newlines(cur_indent, in_global_context=in_global_context)
        formatted = f"{TAB * cur_indent}{self.syntax.keyword_line}"
        if self.syntax.enter_context:
            formatted += ":"
        formatted += f"{self.syntax.comment}\n"
        self.last_recognised_keyword = self.syntax.keyword_name
        # cache to enable sorted context to insert,
        # this always a `run:`, must at the end
        if self.syntax.accepts_python_code:
            self.previous_result += self.result
            self.result = formatted
        else:  # not a PythonCode context, collect keywords to sort
            self.previous_result += self.result + formatted
            self.result = ""
            self.keyword_spec = self.vocab.ordered()

    def process_keyword_param(
        self, param_context: ParameterSyntax, in_global_context: bool
    ):
        self.add_newlines(
            param_context.keyword_indent - 1,
            in_global_context=in_global_context,
            context=param_context,
        )
        param_formatted = self.format_params(param_context)
        if self.fmt_sort_off is None and not in_global_context and self.keyword_spec:
            self.keywords[param_context.keyword_name] = self.result + param_formatted
            self.result = ""
        else:
            self.result += param_formatted
        self.last_recognised_keyword = param_context.keyword_name

    def post_process_keyword(self):
        if not self.previous_result:
            self.previous_result = self.result
            self.result = ""
        for keyword in self.keyword_spec:
            res = self.keywords.pop(keyword, "")
            self.previous_result += res
        assert not self.keywords, (
            "All directives should have been consumed; "
            "if not, this is a bug in snakefmt's handling of snakemake syntax. "
            "It must be the coder's fault, not the user's. "
            "So please report this to the developers with the code so we can fix it: "
            "https://github.com/snakemake/snakefmt/issues"
        )
        self.result = self.previous_result + self.result
        self.previous_result = ""
        # Keep no_formatting_yet when there is pending buffered content.
        # This prevents premature separator insertion after fmt: off/on
        # verbatim regions before the next flush occurs.
        if self.no_formatting_yet and self.result.rstrip("\n") and not self.buffer:
            self.no_formatting_yet = False

    def handle_fmt_off_region(self, verbatim: str) -> None:
        if self.no_formatting_yet:
            self.result = self.result.lstrip("\n")
        self.result += self.buffer
        self.buffer = ""
        if not verbatim:
            return
        # When fmt:off[next] is inside a Python block (e.g. `if 1:`), the
        # directive ends up as a lagging_comment after flushing that block.
        is_nested_next = self.fmt_off and self.fmt_off[1] == "next"
        if self.lagging_comments:
            # For nested fmt:off[next], add the same \n separator that
            # process_keyword_context/add_newlines would normally provide
            # before the first keyword inside the Python block.
            if is_nested_next and not self.no_formatting_yet:
                self.result += "\n"
            self.result += self.lagging_comments
            self.lagging_comments = ""
        if self.fmt_off_preceded_by_blank_line:
            if self.result and not self.result.endswith("\n\n"):
                self.result += "\n"
            self.fmt_off_preceded_by_blank_line = False
        self.result += verbatim
        # For fmt: off[next], mark that we've emitted content so the following
        # block gets its normal blank-line separator.
        # For fmt: off regions, treat verbatim as transparent to separator logic.
        self.no_formatting_yet = not is_nested_next
        self.last_recognised_keyword = ""

    def run_black_format_str(
        self,
        string: str,
        target_indent: int,
        extra_spacing: int = 0,
        no_nesting: bool = False,
    ) -> str:
        """
        `no_nesting`: black uses one line skips between code blocks, instead of two,
        for nested code (e.g. inside 'if'). We emulate this by putting nested code
        inside an artificial 'if' statement. Setting `no_nesting` to True means the code
        will always be formatted with two line skips.
        """
        artificial_nest = (
            (self.from_python or self.syntax.accepts_python_code)
            and target_indent > 0
            and not is_all_comments(string)
            and len(string.strip().splitlines()) > 1
            and not no_nesting
        )
        if artificial_nest:
            string = f"if x:\n{textwrap.indent(string, TAB)}"

        # reduce black target line length according to how indented the code is
        current_line_length = (target_indent or 0) * TAB_SIZE
        black_mode = copy(self.black_mode)
        black_mode.line_length = max(
            0, black_mode.line_length - current_line_length + extra_spacing
        )
        try:
            fmted = black.format_str(string, mode=black_mode)
        except black.parsing.InvalidInput as e:
            err_msg = ""
            # Not clear whether all Black errors start with 'Cannot parse' - it seems to
            # in the tests I ran
            match = re.search(r"(Cannot parse.*?:\s*)(?P<line>\d+)(.*)", str(e))
            try:
                next_token = next(self.snakefile)
                self.snakefile.denext(next_token)
            except StopIteration:
                next_token = None
            if match and next_token is not None:
                # this is the line number within the piece of code that was passed to
                # black, not necessarily the line number within the Snakefile
                line_num = int(match.group("line"))
                context_line_num = next_token.start[0] - len(string.splitlines())
                total_line_num = context_line_num + line_num - 1
                err_msg = match.group(1) + str(total_line_num) + match.group(3)
            elif match and self.last_token is not None:
                # Fallback when next_token is None (e.g. at EOF)
                line_num = int(match.group("line"))
                # Adjustment: last_token is usually a DEDENT or ENDMARKER on the line
                # after the block
                context_line_num = self.last_token.start[0] - len(string.splitlines())

                if self.last_token.type not in (
                    tokenize.DEDENT,
                    tokenize.ENDMARKER,
                ):
                    context_line_num += 1
                total_line_num = context_line_num + line_num - 1
                err_msg = match.group(1) + str(total_line_num) + match.group(3)
                err_msg += (
                    "\n\n(Note reported line number may be an approximation as "
                    "snakefmt reached the end of the file)"
                )
            else:
                err_msg = str(e) + (
                    "\n\n(Note reported line number may be incorrect, as"
                    " snakefmt could not determine the true line number)"
                )
            err_msg = f"Black error:\n```\n{str(err_msg)}\n```\n"
            raise InvalidPython(err_msg) from None

        if artificial_nest:
            lines = fmted.splitlines(keepends=True)[1:]
            s = "".join(lines).lstrip("\n")
            fmted = textwrap.dedent(s)
        return fmted

    def align_strings(self, string: str, target_indent: int) -> str:
        """
        Takes an ensemble of strings and indents/reindents it
        """
        used_indent = TAB * target_indent
        split_string = split_code_string(string)
        if len(split_string) == 1:
            return textwrap.indent(split_string[0], used_indent)

        # First, masks all multi-line strings
        mask_string = "`~!@#$%^&*|?"
        while mask_string in string:
            mask_string += mask_string
        mask_string = f'"""{mask_string}"""'
        fakewrap = textwrap.indent(
            "".join(mask_string if i % 2 else s for i, s in enumerate(split_string)),
            used_indent,
        )
        split_code = fakewrap.split(mask_string)

        # After indenting, we put those strings back exactly as they were
        indented = "".join(
            s.replace("\t", TAB) if i % 2 else split_code[i // 2]
            for i, s in enumerate(split_string)
        )
        return indented

    def format_param(
        self,
        parameter: Parameter,
        target_indent: int,
        inline_formatting: bool,
        param_list: bool = True,
    ) -> str:
        string_indent = TAB * target_indent
        if inline_formatting:
            target_indent = 0
        val = str(parameter)

        try:
            # A snakemake parameter is syntactically like a function parameter
            ast_parse(f"param({val})")
        except SyntaxError:
            raise InvalidParameterSyntax(f"{parameter.line_nb}{val}") from None

        val = val.rstrip()

        # Wrapping trick to avoid Black 26 standalone string reformatting
        val = f"f({val})"
        extra_spacing = 3

        try:
            val = self.run_black_format_str(
                val, target_indent, extra_spacing, no_nesting=True
            )
        except InvalidPython:
            # Fallback for cases like https://github.com/snakemake/snakefmt/issues/129
            val = f"({val})"
            val = self.run_black_format_str(
                val, target_indent, extra_spacing, no_nesting=True
            )

        val_stripped = val.strip()
        is_multiline_fallback = False
        if match_fallback := re.match(
            r"^\(\s*(f\(.*\))\s*\)$", val_stripped, re.DOTALL
        ):
            if "\n" in val_stripped[: match_fallback.start(1)]:
                is_multiline_fallback = True
            val_stripped = match_fallback.group(1)

        if match_f := re.match(r"^f\((.*)\)$", val_stripped, re.DOTALL):
            content = match_f.group(1)
            if content.startswith("\n"):
                content = content[1:]

                # Split the string and only dedent the code parts to strip
                # Black's spaces
                parts = split_code_string(content)
                new_parts = []
                for i, p in enumerate(parts):
                    if i % 2 == 0:
                        # Code part: strip 4 spaces
                        # (or 8 spaces if multiline fallback wrapper was used)
                        strip_pattern = r"^ {8}" if is_multiline_fallback else r"^ {4}"
                        p = re.sub(strip_pattern, "", p, flags=re.MULTILINE)
                    # String part: leave alone!
                    new_parts.append(p)

                val = "".join(new_parts)
                val = val.rstrip("\n")
            else:
                val = content

        val = self.align_strings(val, target_indent)

        result = ""
        if not inline_formatting:
            for comment in parameter.pre_comments:
                result += f"{string_indent}{comment}\n"
        result += val.strip("\n")
        if param_list:
            result += ","
        post_comment_iter = iter(parameter.post_comments)
        if parameter._has_inline_comment:
            result += f"{COMMENT_SPACING}{next(post_comment_iter)}"
        result += "\n"
        for comment in post_comment_iter:
            result += f"{string_indent}{comment}\n"
        return result

    def format_params(self, parameters: ParameterSyntax) -> str:
        keyword_line_nb = self.current_line_nb
        target_indent = parameters.keyword_indent
        used_indent = TAB * (target_indent - 1)

        p_class = parameters.__class__
        param_list = issubclass(p_class, ParamList)
        inline_fmting = p_class is InlineSingleParam

        result = f"{used_indent}{parameters.keyword_line}:"
        if inline_fmting:
            # here, check if the value is too large to put in one line
            param = parameters.all_params[0]
            param_result = self.format_param(
                param, target_indent, inline_fmting, param_list
            )
            inline_fmting = param_result.count("\n") == 1
        if inline_fmting:
            prepended_comments = ""
            if parameters.comment != "":
                prepended_comments += f"{used_indent}{parameters.comment.lstrip()}\n"
            for comment in param.pre_comments:
                prepended_comments += f"{used_indent}{comment}\n"
            if prepended_comments != "":
                keyword_line_nb += prepended_comments.count("\n")
                Warnings.comment_relocation(parameters.keyword_name, keyword_line_nb)
            result = f"{prepended_comments}{result} {param_result}"
        else:
            result = f"{result}{parameters.comment}\n"
            for param in parameters.all_params:
                result += self.format_param(
                    param, target_indent, inline_fmting, param_list
                )
        num_c = len(param.post_comments)
        if num_c > 1 or (not param._has_inline_comment and num_c == 1):
            Warnings.block_comment_below(parameters.keyword_name, keyword_line_nb)
        return result

    def add_newlines(
        self,
        cur_indent: int,
        formatted_string: str = "",
        final_flush: bool = False,
        in_global_context: bool = False,
        context: Optional[Syntax] = None,
    ):
        """
        Top-level (indent of 0) rules and python code get two newlines separation
        Indented rules/pycode get one newline separation
        Comments immediately preceding rules/pycode get newlined with them
        """
        comment_matches = 0
        comment_break = 1
        all_lines = formatted_string.splitlines()
        if len(all_lines) > 0:
            for line in reversed(all_lines):
                if not comment_start(line):
                    break
                comment_matches += 1
            comment_break = len(all_lines) - comment_matches

        have_only_comment_lines = comment_break == 0
        if not have_only_comment_lines or final_flush:
            collate_same_singleparamkeyword = (
                context is not None
                and context.keyword_name == self.last_recognised_keyword
                and issubclass(context.__class__, SingleParam)
            )
            if not self.no_formatting_yet and not collate_same_singleparamkeyword:
                after_if_statement = self.buffer.startswith(after_if_keywords)
                if max(cur_indent, 0) in (0, None) and not after_if_statement:
                    self.result += "\n\n"
                elif in_global_context or after_if_statement:
                    self.result += "\n"
        if in_global_context:  # Deal with comments
            if self.lagging_comments != "":
                self.result += self.lagging_comments
                self.lagging_comments = ""

            if len(all_lines) > 0:
                if not have_only_comment_lines:
                    self.result += "\n".join(all_lines[:comment_break]).rstrip() + "\n"
                if comment_matches > 0:
                    self.lagging_comments = "\n".join(all_lines[comment_break:]) + "\n"
                    if final_flush:
                        self.result += self.lagging_comments
        else:
            self.result += formatted_string

        if self.no_formatting_yet:
            if comment_break > 0:
                self.no_formatting_yet = False
