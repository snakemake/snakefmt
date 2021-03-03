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


class Grammar(NamedTuple):
    """
    Ties together a vocabulary and a context (=syntax reader)
    When a keyword from `vocab` is recognised, a new grammar is induced
    """

    vocab: Optional[Union[Type[Vocabulary], Vocabulary]]
    context: Union[Type[Syntax], Syntax]


class PythonCode(Vocabulary):
    pass


# In common between 'use rule' and 'rule'
rule_properties = dict(
    name=Grammar(None, SingleParam),
    input=Grammar(None, ParamList),
    output=Grammar(None, ParamList),
    params=Grammar(None, ParamList),
    threads=Grammar(None, InlineSingleParam),
    resources=Grammar(None, ParamList),
    priority=Grammar(None, InlineSingleParam),
    version=Grammar(None, SingleParam),
    log=Grammar(None, ParamList),
    message=Grammar(None, SingleParam),
    benchmark=Grammar(None, SingleParam),
    conda=Grammar(None, SingleParam),
    singularity=Grammar(None, SingleParam),
    container=Grammar(None, SingleParam),
    containerized=Grammar(None, SingleParam),
    envmodules=Grammar(None, NoKeyParamList),
    wildcard_constraints=Grammar(None, ParamList),
    shadow=Grammar(None, SingleParam),
    group=Grammar(None, SingleParam),
    cache=Grammar(None, InlineSingleParam),
)


class SnakeUseRule(Vocabulary):
    spec = rule_properties


class SnakeRule(Vocabulary):
    spec = dict(
        run=Grammar(PythonCode, KeywordSyntax),
        shell=Grammar(None, SingleParam),
        script=Grammar(None, SingleParam),
        notebook=Grammar(None, SingleParam),
        wrapper=Grammar(None, SingleParam),
        cwl=Grammar(None, SingleParam),
        **rule_properties
    )


class SnakeModule(Vocabulary):
    spec = dict(
        snakefile=Grammar(None, SingleParam),
        config=Grammar(None, SingleParam),
        skip_validation=Grammar(None, SingleParam),
        meta_wrapper=Grammar(None, SingleParam),
        replace_prefix=Grammar(None, SingleParam),
    )


class SnakeSubworkflow(Vocabulary):
    spec = dict(
        snakefile=Grammar(None, SingleParam),
        workdir=Grammar(None, SingleParam),
        configfile=Grammar(None, SingleParam),
    )


class SnakeGlobal(Vocabulary):
    spec = dict(
        envvars=Grammar(None, NoKeyParamList),
        include=Grammar(None, InlineSingleParam),
        workdir=Grammar(None, InlineSingleParam),
        configfile=Grammar(None, InlineSingleParam),
        pepfile=Grammar(None, InlineSingleParam),
        pepschema=Grammar(None, InlineSingleParam),
        report=Grammar(None, InlineSingleParam),
        ruleorder=Grammar(None, InlineSingleParam),
        rule=Grammar(SnakeRule, KeywordSyntax),
        checkpoint=Grammar(SnakeRule, KeywordSyntax),
        subworkflow=Grammar(SnakeSubworkflow, KeywordSyntax),
        localrules=Grammar(None, NoKeyParamList),
        onstart=Grammar(PythonCode, KeywordSyntax),
        onsuccess=Grammar(PythonCode, KeywordSyntax),
        onerror=Grammar(PythonCode, KeywordSyntax),
        wildcard_constraints=Grammar(None, ParamList),
        singularity=Grammar(None, InlineSingleParam),
        container=Grammar(None, InlineSingleParam),
        containerized=Grammar(None, InlineSingleParam),
        scattergather=Grammar(None, ParamList),
        module=Grammar(SnakeModule, KeywordSyntax),
        use=Grammar(SnakeUseRule, KeywordSyntax),
    )
