from collections import OrderedDict
from typing import Optional, TypeVar

from snakefmt.parser.blocks import NamedBlock
from snakefmt.parser.snakemake_blocks import (
    SnakemakeArgumentsBlock,
    SnakemakeBlock,
    SnakemakeDirectiveBlock,
    SnakemakeExecutableBlock,
    SnakemakeInlineArgumentBlock,
    SnakemakeUnnamedArgumentBlock,
    SnakemakeUnnamedArgumentsBlock,
    Use,
)


def _init_block_register():
    T = TypeVar("T", bound=SnakemakeBlock)

    def register_block(name: Optional[str] = None):
        def decorator(type_: type[T]) -> type[T]:
            keyword = name or type_._keyword()
            namespace[keyword] = type_
            return type_

        return decorator

    namespace: OrderedDict[str, type[SnakemakeBlock]] = OrderedDict()
    return namespace, register_block


global_snakemake_subautomata, _register = _init_block_register()


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


@_register()
class Module(NamedBlock, SnakemakeDirectiveBlock):
    subautomata, _register = _init_block_register()

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


class _Rule(NamedBlock, SnakemakeDirectiveBlock):
    subautomata, _register = _init_block_register()

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
class UseRule(Use):

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
    exec_subautomata, _register = _init_block_register()

    @_register()
    class Run(SnakemakeExecutableBlock): ...

    class AbstractCmd(SnakemakeUnnamedArgumentBlock, Run): ...

    @_register()
    class Shell(AbstractCmd): ...

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
