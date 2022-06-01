from typing import NamedTuple, Optional, Type, Union

from snakefmt.parser.syntax import (
    InlineSingleParam,
    KeywordSyntax,
    NoKeyParamList,
    ParamList,
    SingleParam,
    Syntax,
    Vocabulary,
)


class Context(NamedTuple):
    """
    Ties together a vocabulary and a syntax.
    When a keyword from `vocab` is recognised, a new context is induced
    """

    vocab: Optional[Union[Type[Vocabulary], Vocabulary]]
    syntax: Union[Type[Syntax], Syntax]


class PythonCode(Vocabulary):
    pass


# In common between 'use rule' and 'rule'
rule_properties = dict(
    name=Context(None, SingleParam),
    input=Context(None, ParamList),
    output=Context(None, ParamList),
    params=Context(None, ParamList),
    threads=Context(None, InlineSingleParam),
    resources=Context(None, ParamList),
    priority=Context(None, InlineSingleParam),
    version=Context(None, SingleParam),
    log=Context(None, ParamList),
    message=Context(None, SingleParam),
    benchmark=Context(None, SingleParam),
    conda=Context(None, SingleParam),
    singularity=Context(None, SingleParam),
    container=Context(None, SingleParam),
    containerized=Context(None, SingleParam),
    envmodules=Context(None, NoKeyParamList),
    wildcard_constraints=Context(None, ParamList),
    shadow=Context(None, SingleParam),
    group=Context(None, SingleParam),
    cache=Context(None, InlineSingleParam),
    handover=Context(None, InlineSingleParam),
    default_target=Context(None, InlineSingleParam),
    retries=Context(None, InlineSingleParam),
)


class SnakeUseRule(Vocabulary):
    spec = rule_properties


class SnakeRule(Vocabulary):
    spec = dict(
        run=Context(PythonCode, KeywordSyntax),
        shell=Context(None, SingleParam),
        script=Context(None, SingleParam),
        notebook=Context(None, SingleParam),
        wrapper=Context(None, SingleParam),
        cwl=Context(None, SingleParam),
        template_engine=Context(None, SingleParam),
        **rule_properties
    )


class SnakeModule(Vocabulary):
    spec = dict(
        snakefile=Context(None, SingleParam),
        config=Context(None, SingleParam),
        skip_validation=Context(None, SingleParam),
        meta_wrapper=Context(None, SingleParam),
        prefix=Context(None, SingleParam),
        replace_prefix=Context(None, SingleParam),
    )


class SnakeSubworkflow(Vocabulary):
    spec = dict(
        snakefile=Context(None, SingleParam),
        workdir=Context(None, SingleParam),
        configfile=Context(None, SingleParam),
    )


class SnakeGlobal(Vocabulary):
    spec = dict(
        envvars=Context(None, NoKeyParamList),
        include=Context(None, InlineSingleParam),
        workdir=Context(None, InlineSingleParam),
        configfile=Context(None, InlineSingleParam),
        pepfile=Context(None, InlineSingleParam),
        pepschema=Context(None, InlineSingleParam),
        report=Context(None, InlineSingleParam),
        ruleorder=Context(None, InlineSingleParam),
        rule=Context(SnakeRule, KeywordSyntax),
        checkpoint=Context(SnakeRule, KeywordSyntax),
        subworkflow=Context(SnakeSubworkflow, KeywordSyntax),
        localrules=Context(None, NoKeyParamList),
        onstart=Context(PythonCode, KeywordSyntax),
        onsuccess=Context(PythonCode, KeywordSyntax),
        onerror=Context(PythonCode, KeywordSyntax),
        wildcard_constraints=Context(None, ParamList),
        singularity=Context(None, InlineSingleParam),
        container=Context(None, InlineSingleParam),
        containerized=Context(None, InlineSingleParam),
        scattergather=Context(None, ParamList),
        module=Context(SnakeModule, KeywordSyntax),
        use=Context(SnakeUseRule, KeywordSyntax),
    )
