import io
import re
import tokenize
from collections import OrderedDict
from tokenize import TokenInfo
from typing import Optional, TypeVar

from snakefmt.config import Mode
from snakefmt.exceptions import (
    ColonError,
    EmptyContextError,
    InvalidParameterSyntax,
    SyntaxFormError,
    UnsupportedSyntax,
)
from snakefmt.parser.blocks import (
    NamedBlock,
    PythonBlock,
    SnakemakeArgumentsBlock,
    SnakemakeBlock,
    SnakemakeExecutableBlock,
    SnakemakeInlineArgumentBlock,
    SnakemakeUnnamedArgumentBlock,
    SnakemakeUnnamedArgumentsBlock,
)
from snakefmt.parser.formatting import FormatState
from snakefmt.parser.tokens import (
    TAB,
    deindent_lines,
    effective,
    is_op,
    line_nb,
    tokens2linestrs,
)
from snakefmt.shell_formatter import format_python_string_literal

from . import formatting


def init_block_register():
    T = TypeVar("T", bound=SnakemakeBlock)

    def register_block(name: Optional[str] = None):
        def decorator(type_: type[T]) -> type[T]:
            keyword = name or type_._keyword()
            namespace[keyword] = type_
            return type_

        return decorator

    namespace: OrderedDict[str, type[SnakemakeBlock]] = OrderedDict()
    return namespace, register_block


global_snakemake_subautomata, _register = init_block_register()


@_register()
class Include(SnakemakeInlineArgumentBlock): ...


@_register()
class Workdir(SnakemakeInlineArgumentBlock): ...


@_register()
class Configfile(SnakemakeInlineArgumentBlock): ...


@_register("pepfile")
class Set_Pepfile(SnakemakeInlineArgumentBlock): ...


@_register()
class Pepschema(SnakemakeInlineArgumentBlock): ...


@_register()
class Report(SnakemakeInlineArgumentBlock): ...


@_register()
class Ruleorder(SnakemakeInlineArgumentBlock): ...


@_register("singularity")
@_register("container")
class Global_Container(SnakemakeInlineArgumentBlock): ...


@_register("containerized")
class Global_Containerized(SnakemakeInlineArgumentBlock): ...


@_register("conda")
class Global_Conda(SnakemakeInlineArgumentBlock): ...


@_register("envvars")
class Register_Envvars(SnakemakeUnnamedArgumentsBlock): ...


@_register()
class Localrules(SnakemakeUnnamedArgumentsBlock): ...


@_register()
class InputFlags(SnakemakeUnnamedArgumentsBlock): ...


@_register()
class OutputFlags(SnakemakeUnnamedArgumentsBlock): ...


@_register("wildcard_constraints")
class Global_Wildcard_Constraints(SnakemakeArgumentsBlock): ...


@_register()
class Scattergather(SnakemakeArgumentsBlock): ...


@_register("resource_scopes")
class ResourceScope(SnakemakeArgumentsBlock): ...


@_register()
class Storage(SnakemakeArgumentsBlock):
    nameable = True


@_register("pathvars")
class Register_Pathvars(SnakemakeArgumentsBlock): ...


@_register()
class OnStart(SnakemakeExecutableBlock): ...


@_register()
class OnSuccess(SnakemakeExecutableBlock): ...


@_register()
class OnError(SnakemakeExecutableBlock): ...


class SnakemakeDirectiveBlock(SnakemakeBlock):
    """Block of snakemake directives, such as `rule:`, `module:`, etc.
    The contents are other snakemake blocks.
    """

    nameable = True

    def consume_body(self, tokens):
        blocks = self.consume_subblocks(tokens, ender_subblock=True)
        keyword = self.colon_line.body[0].string
        no_content = True
        for block in blocks:
            if isinstance(block, SnakemakeBlock):
                no_content = False
                continue
            if not isinstance(block, PythonBlock):
                rep = block.start_token or self.start_token
                raise UnsupportedSyntax(
                    f"{line_nb(rep)}Unexpected content in "
                    f"{keyword} block: {rep.line}"
                )
            code = [
                token
                for line in block.head_lines
                for token in line.iter
                if effective(token)
            ]
            if len(code) == 1 and code[0].type == tokenize.STRING:
                no_content = False
                continue
            if not code:
                continue
            rep = block.start_token
            if rep is not None:
                if rep.type == tokenize.NAME:
                    raise SyntaxError(
                        f"{line_nb(rep)}Unrecognised keyword "
                        f"{rep.string!r} in {keyword} definition"
                    )
            else:
                rep = self.start_token
            raise SyntaxError(
                f"{line_nb(rep)}Invalid python code in "
                f"{keyword} definition: {rep.line}"
            )
        if no_content:
            raise EmptyContextError(
                f"{line_nb(self.colon_line.body[0])}{keyword} has no "
                f"keywords attached to it."
            )
        self.body_blocks = blocks

    def directive_order(self, state: FormatState) -> tuple[str, ...]:
        """Directive order used when sorting this block's directives."""
        return state.rule_order

    def format_body(self, mode, state, post_colon):
        """Sort directives in the order of subautomata,
        and format them together with the head line.
        """
        assert not post_colon, "Invalid inline contents"
        formatted: list[str] = []
        directives: dict[str, str] = {}
        tail_noncoding: list[str] = []
        indent = TAB * (self.deindent_level + 1)
        order = self.directive_order(state)
        for block in self.body_blocks:
            assert not tail_noncoding, "no tail_noncoding before body_blocks"
            if isinstance(block, PythonBlock):
                formatted.append(block.formatted(mode))
                for line in block.head_linestrs:
                    state = state.update(line.lstrip())
                # A blank line the user wrote between the docstring
                # and the first directive is kept
                if len(self.body_blocks) > 1:
                    block = self.body_blocks[1]
                    assert isinstance(
                        block, SnakemakeBlock
                    ), "Unexpected block type in snakemake keyword block"
                    following = block.colon_line.head_noncoding
                    if following and following[0].type == tokenize.NL:
                        formatted.append("\n")
                continue
            assert isinstance(
                block, SnakemakeBlock
            ), "Unexpected block type in snakemake keyword block"
            noncoding = tokens2linestrs(iter(block.colon_line.head_noncoding))
            directive = ""
            for line in noncoding:  # here noncoding is already formated
                linelstrip = line.lstrip()
                last_sort_off = state.sort_directives
                if linelstrip:
                    # only non-empty lines are formattable
                    if state.found_skip(linelstrip):
                        directive += line
                    else:
                        directive += indent + formatting.format_black(
                            linelstrip, mode, 0
                        )
                    state = state.update(linelstrip)
                if state.not_format:
                    if directives:
                        formatted.extend(self.sort_directives(directives, order))
                    if directive:
                        formatted.append(directive)
                        directive = ""
                    if not linelstrip:
                        formatted.extend(
                            deindent_lines(
                                block.indent_str, self.deindent_level + 1, [line]
                            )
                        )
                elif not state.sort_directives:
                    if directives:
                        formatted.extend(self.sort_directives(directives, order))
                    if directive:
                        formatted.append(directive)
                        directive = ""
                elif not last_sort_off:
                    # state.sort_directives switched on, this comment is
                    #  actually `# fmt: on[sort]` directive,
                    # so split from next directive
                    formatted.append(directive)
                    directive = ""
            if state.not_format:
                formatted.extend(
                    deindent_lines(
                        block.indent_str,
                        self.deindent_level + 1,
                        block.raw_source_linestrs(),
                    )
                )
            else:
                directive += block.formatted(mode, state)
                if state.sort_directives:
                    directives[block.start_token.string] = directive
                else:
                    assert not directives, "Already flushed once fmt: off[sort]"
                    formatted.append(directive)
            if block.tail_noncoding:
                tail_noncoding = tokens2linestrs(iter(block.tail_noncoding))
            # no `\n` between
        if directives:
            formatted.extend(self.sort_directives(directives, order))
        if tail_noncoding:
            tail_noncoding = [i.lstrip().rstrip("\n") for i in tail_noncoding]
            formatted.extend(f"{indent}{i}\n" for i in tail_noncoding if i)
        return "".join(formatted)

    @classmethod
    def sort_directives(cls, directives: dict[str, str], order: tuple[str, ...] = ()):
        """Yield the directives sorted by `order`, then by the subautomata order
        for any directive not listed. Clears `directives`."""
        seen: set[str] = set()
        for keyword in (*order, *cls.subautomata):
            if keyword not in seen and keyword in directives:
                seen.add(keyword)
                yield directives.pop(keyword)
        assert not directives, f"Unknown directives: {', '.join(directives)}"


@_register()
class Module(NamedBlock, SnakemakeDirectiveBlock):
    subautomata, _register = init_block_register()

    @_register()
    class Name(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Pathvars(SnakemakeArgumentsBlock): ...

    # Reference
    @_register()
    class Snakefile(SnakemakeUnnamedArgumentBlock): ...

    # Override
    @_register()
    class Config(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Skip_Validation(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Prefix(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Replace_Prefix(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Meta_Wrapper(SnakemakeUnnamedArgumentBlock): ...

    def directive_order(self, state: FormatState) -> tuple[str, ...]:
        return state.module_order


class _Rule(NamedBlock, SnakemakeDirectiveBlock):
    subautomata, _register = init_block_register()

    @_register()
    class Name(SnakemakeUnnamedArgumentBlock): ...

    @_register("default_target")
    class Default_Target_Rule(SnakemakeInlineArgumentBlock): ...

    # I/O
    @_register()
    class Input(SnakemakeArgumentsBlock): ...

    @_register()
    class Output(SnakemakeArgumentsBlock): ...

    @_register()
    class Log(SnakemakeArgumentsBlock): ...

    @_register()
    class Benchmark(SnakemakeUnnamedArgumentBlock): ...

    # Rule logic
    @_register()
    class Pathvars(SnakemakeArgumentsBlock): ...

    @_register("wildcard_constraints")
    class Register_Wildcard_Constraints(SnakemakeArgumentsBlock): ...

    # Scheduling & control
    @_register("cache")
    class Cache_Rule(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Priority(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Retries(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Group(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class LocalRule(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Handover(SnakemakeInlineArgumentBlock): ...

    # Execution environment
    @_register()
    class Shadow(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Conda(SnakemakeUnnamedArgumentBlock): ...

    @_register("singularity")
    @_register()
    class Container(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class Containerized(SnakemakeUnnamedArgumentBlock): ...

    @_register()
    class EnvModules(SnakemakeUnnamedArgumentsBlock): ...

    # Execution resources and parameters

    @_register()
    class Threads(SnakemakeInlineArgumentBlock): ...

    @_register()
    class Resources(SnakemakeArgumentsBlock): ...

    @_register()
    class Params(SnakemakeArgumentsBlock): ...

    # Runtime messages
    @_register()
    class Message(SnakemakeUnnamedArgumentBlock): ...

    deprecated = {"version": "Use conda or container directive instead (see docs)."}


@_register("use")
class UseRule(_Rule):

    _EBNF = (
        '"use" "rule" (identifier | "*") '
        '"from" identifier '
        '["exclude" identifier {"," identifier}] '
        '["as" identifier] ["with" ":"]'
    )

    def validate_head(self, allow_suffix=False):
        body = self.colon_line.body
        line = body[0].line.split("#", 1)[0].strip()

        def fail():
            raise SyntaxFormError(line_nb(body[0]), line, self._EBNF)

        def is_identifier(token: str):
            return re.fullmatch(r"[a-zA-Z_]\w*", token) is not None

        def is_glob(token: str):
            return re.fullmatch(r"[a-zA-Z_][\w*]*", token) is not None

        # commas may be surrounded by spaces; make them separate tokens
        tokens = line.replace(",", " , ").split()
        if tokens[:2] != ["use", "rule"]:
            fail()

        # reading a *required* token past the end is a syntax error, so those
        # reads are left unguarded and `IndexError` -> `fail()`. Optional
        # trailing parts (e.g. `from ...` alone) are guarded with `i < len`.
        try:
            whitelist = [tokens[2]]
            i = 3
            # the whitelist must be followed by a keyword, so running past the
            # end here is a syntax error (IndexError -> fail())
            while tokens[i] == ",":
                whitelist.append(tokens[i + 1])
                i += 2
            if whitelist != ["*"]:
                if "*" in whitelist:
                    raise InvalidParameterSyntax(
                        "'*' cannot be used with other rule names in the use directive"
                    )
                if not all(is_identifier(name) for name in whitelist):
                    fail()
            if tokens[i] not in ("from", "as", "with", "with:"):
                fail()

            # module: the source after `from`
            if tokens[i] == "from":
                i += 1
                module = tokens[i]
                if not is_identifier(module):
                    fail()
                i += 1
            else:
                module = None
        except IndexError:
            fail()

        # exclude: comma separated rule names after `exclude`
        token_length = len(tokens)
        exclude: list[str] = []
        rename = None
        try:
            # exclude: comma separated rule names after `exclude`
            if i < token_length and tokens[i] == "exclude":
                exclude.append(tokens[i + 1])
                i += 2
                while i < token_length and tokens[i] == ",":
                    exclude.append(tokens[i + 1])
                    i += 2
                if not all(is_identifier(name) for name in exclude):
                    fail()
            # modifier: the alias after `as`
            if i < token_length and tokens[i] == "as":
                rename = tokens[i + 1]
                if not is_glob(rename):
                    fail()
                i += 2
        except IndexError:
            fail()

        if "".join(tokens[i:]) not in ("", "with:"):
            fail()

        if module is None and rename is None:
            raise InvalidParameterSyntax(
                "use directive must specify a rule from a module or modify the rule"
            )

        self.whitelist = whitelist
        self.module = module
        self.exclude = exclude
        self.rename = rename

    def consume_body(self, tokens):
        super().consume_body(tokens)
        for block in self.body_blocks:
            if isinstance(block, SnakemakeArgumentsBlock):
                body = block.colon_line.body
                # nameable children here take `with`, nothing else
                if not is_op(":", body[1]) and body[1].string != "with":
                    ColonError(line_nb(body[1]), body[1].string, body[0].string)

    def formatted(self, mode, state):
        """Allow:
        use rule * from other_workflow exclude ruleC as other_*
        use rule * from other_workflow exclude ruleC
        use rule * from other_workflow as other_*
        use rule * from other_workflow
        use rule a,b from other_workflow
        """
        assert len(self.head_lines) == 1, "use directive should only have one head line"
        head_line = tokens2linestrs(iter(self.head_lines[0].body))
        assert len(head_line) == 1, "use directive should be single line"
        head_bulk_line = head_line[0].split("#", 1)[0]
        if ":" not in head_bulk_line:
            # return quickly (also no body block here)
            indent = TAB * self.deindent_level
            components = head_bulk_line.strip().split()
            formatted_head = indent + " ".join(components)
            if "#" in head_line[0]:
                formatted_head += "  " + formatting.format_black(
                    "#" + head_line[0].split("#", 1)[1], mode=mode
                ).rstrip("\n")
            return formatted_head + "\n"
        formatted_prior, post_colon = self.format_head(mode)
        formatted_body = self.format_body(mode, state, post_colon)
        formatted = [formatted_prior, formatted_body]
        return "".join(formatted)

    subautomata = {**_Rule.subautomata} | {
        keyword: type(keyword, (_Rule.subautomata[keyword],), {"nameable": True})
        for keyword in (
            "input",
            "output",
            "log",
            "pathvars",
            "wildcard_constraints",
            "resources",
            "params",
        )
    }


@_register()
class Rule(_Rule):
    # Action
    exec_subautomata, _register = init_block_register()

    @_register()
    class Run(SnakemakeExecutableBlock): ...

    class AbstractCmd(SnakemakeUnnamedArgumentBlock, Run): ...

    @_register()
    class Shell(AbstractCmd):
        def format_body(
            self, mode: Mode, state: FormatState, post_colon: list[TokenInfo]
        ) -> str:
            """Format the body, then (if enabled) reformat its lone string
            literal as shell code with `shfmt`.

            Going through the normal body formatting first keeps surrounding
            comments/blank lines and the trailing-comma handling; only the
            literal itself is then swapped for its `shfmt`'ed form.
            """
            formatted = super().format_body(mode, state, post_colon)
            if not state.format_shell:
                return formatted
            strings = [
                token
                for token in tokenize.generate_tokens(io.StringIO(formatted).readline)
                if token.type == tokenize.STRING
            ]
            if len(strings) != 1:
                return formatted
            (string,) = strings
            lines = formatted.splitlines(keepends=True)
            start = (
                sum(len(line) for line in lines[: string.start[0] - 1])
                + string.start[1]
            )
            end = sum(len(line) for line in lines[: string.end[0] - 1]) + string.end[1]
            return (
                formatted[:start]
                + format_python_string_literal(
                    formatted[start:end], self.deindent_level + 1
                )
                + formatted[end:]
            )

    @_register()
    class Script(AbstractCmd): ...

    @_register()
    class Notebook(Script): ...

    @_register()
    class Wrapper(Script): ...

    @_register()
    class CWL(Script): ...

    @_register("template_engine")
    class TemplateEngine(Script): ...

    subautomata = {**_Rule.subautomata, **exec_subautomata}


@_register()
class Checkpoint(Rule): ...
