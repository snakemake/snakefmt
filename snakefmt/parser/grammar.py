from typing import NamedTuple, Optional, Type, Union

from snakefmt.parser.syntax import (
    KeywordSyntax,
    NoKeywordParamList,
    ParamList,
    RuleInlineSingleParam,
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


class SnakeRule(Vocabulary):
    spec = dict(
        input=Grammar(None, ParamList),
        output=Grammar(None, ParamList),
        params=Grammar(None, ParamList),
        threads=Grammar(None, RuleInlineSingleParam),
        resources=Grammar(None, ParamList),
        priority=Grammar(None, RuleInlineSingleParam),
        version=Grammar(None, SingleParam),
        log=Grammar(None, ParamList),
        message=Grammar(None, SingleParam),
        benchmark=Grammar(None, SingleParam),
        conda=Grammar(None, SingleParam),
        singularity=Grammar(None, SingleParam),
        container=Grammar(None, SingleParam),
        envmodules=Grammar(None, NoKeywordParamList),
        wildcard_constraints=Grammar(None, ParamList),
        shadow=Grammar(None, SingleParam),
        group=Grammar(None, SingleParam),
        run=Grammar(PythonCode, KeywordSyntax),
        shell=Grammar(None, SingleParam),
        script=Grammar(None, SingleParam),
        notebook=Grammar(None, SingleParam),
        wrapper=Grammar(None, SingleParam),
        cwl=Grammar(None, SingleParam),
        cache=Grammar(None, RuleInlineSingleParam),
    )


class SnakeSubworkflow(Vocabulary):
    spec = dict(
        snakefile=Grammar(None, SingleParam),
        workdir=Grammar(None, SingleParam),
        configfile=Grammar(None, SingleParam),
    )


class SnakeGlobal(Vocabulary):
    spec = dict(
        envvars=Grammar(None, NoKeywordParamList),
        include=Grammar(None, SingleParam),
        workdir=Grammar(None, SingleParam),
        configfile=Grammar(None, SingleParam),
        pepfile=Grammar(None, SingleParam),
        pepschema=Grammar(None, SingleParam),
        report=Grammar(None, SingleParam),
        ruleorder=Grammar(None, SingleParam),
        rule=Grammar(SnakeRule, KeywordSyntax),
        checkpoint=Grammar(SnakeRule, KeywordSyntax),
        subworkflow=Grammar(SnakeSubworkflow, KeywordSyntax),
        localrules=Grammar(None, NoKeywordParamList),
        onstart=Grammar(PythonCode, KeywordSyntax),
        onsuccess=Grammar(PythonCode, KeywordSyntax),
        onerror=Grammar(PythonCode, KeywordSyntax),
        wildcard_constraints=Grammar(None, ParamList),
        scattergather=Grammar(None, ParamList),
        singularity=Grammar(None, SingleParam),
        container=Grammar(None, SingleParam),
    )
