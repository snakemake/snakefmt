from typing import Tuple
from .syntax import (
    namedtuple,
    KeywordSyntax,
    ParamList,
    NoKeywordParamList,
    SingleParam,
    StringParam,
    NumericParam,
)


class Language:
    spec = dict()

    def recognises(self, keyword: str) -> bool:
        if keyword in self.spec:
            return True
        return False

    def get(self, keyword: str) -> Tuple:
        return self.spec[keyword]


Grammar = namedtuple("Grammar", ["language", "context"])

PythonCode = Language  # Alias
accept_python_code = {"run", "onstart", "onsuccess", "onerror"}


class SnakeRule(Language):
    spec = dict(
        input=Grammar(None, ParamList),
        output=Grammar(None, ParamList),
        params=Grammar(None, ParamList),
        threads=Grammar(None, SingleParam),
        resources=Grammar(None, ParamList),
        priority=Grammar(None, NumericParam),
        version=Grammar(None, SingleParam),
        log=Grammar(None, ParamList),
        message=Grammar(None, StringParam),
        benchmark=Grammar(None, SingleParam),
        conda=Grammar(None, StringParam),
        singularity=Grammar(None, StringParam),
        envmodules=Grammar(None, NoKeywordParamList),
        wildcard_constraints=Grammar(None, ParamList),
        shadow=Grammar(None, SingleParam),
        group=Grammar(None, StringParam),
        run=Grammar(PythonCode, KeywordSyntax),
        shell=Grammar(None, SingleParam),
        script=Grammar(None, StringParam),
        notebook=Grammar(None, SingleParam),
        wrapper=Grammar(None, SingleParam),
        cwl=Grammar(None, SingleParam),
    )


class SnakeSubworkflow(Language):
    spec = dict(
        snakefile=Grammar(None, SingleParam),
        workdir=Grammar(None, SingleParam),
        configfile=Grammar(None, SingleParam),
    )


class SnakeGlobal(Language):
    spec = dict(
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
    )
