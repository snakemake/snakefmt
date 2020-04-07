from typing import NamedTuple, Optional, Type, Union

from snakefmt.parser.syntax import (
    Syntax,
    KeywordSyntax,
    ParamList,
    NoKeywordParamList,
    SingleParam,
    RuleInlineSingleParam,
)


class Language:
    spec = dict()

    def recognises(self, keyword: str) -> bool:
        if keyword in self.spec:
            return True
        return False

    def get(self, keyword: str):
        return self.spec[keyword]


class Grammar(NamedTuple):
    language: Optional[Language]
    context: Union[Type[Syntax], Syntax]


PythonCode = Language  # Alias


class SnakeRule(Language):
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


class SnakeSubworkflow(Language):
    spec = dict(
        snakefile=Grammar(None, SingleParam),
        workdir=Grammar(None, SingleParam),
        configfile=Grammar(None, SingleParam),
    )


class SnakeGlobal(Language):
    spec = dict(
        envvars=Grammar(None, NoKeywordParamList),
        include=Grammar(None, SingleParam),
        workdir=Grammar(None, SingleParam),
        configfile=Grammar(None, SingleParam),
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
        singularity=Grammar(None, SingleParam),
        container=Grammar(None, SingleParam),
    )
