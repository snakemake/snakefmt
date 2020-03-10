from typing import Tuple
from .syntax import (
    namedtuple,
    KeywordSyntax,
    ParamList,
    StringNoKeywordParamList,
    SingleParam,
    StringParam,
    NumericParam,
)


class Language:
    spec = dict()

    def recognises(self, keyword: str) -> bool:
        if self.spec.get(keyword, None) is not None:
            return True
        return False

    def get(self, keyword: str) -> Tuple:
        return self.spec[keyword]


Grammar = namedtuple("Grammar", ["language", "context"])


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
        envmodules=Grammar(None, StringNoKeywordParamList),
        wildcard_constraints=Grammar(None, ParamList),
        shadow=Grammar(None, SingleParam),
        group=Grammar(None, StringParam),
        run=Grammar(Language, KeywordSyntax),
        shell=Grammar(None, SingleParam),
        script=Grammar(None, StringParam),
    )


class SnakeGlobal(Language):
    spec = dict(
        include=Grammar(None, StringParam),
        workdir=Grammar(None, StringParam),
        configfile=Grammar(None, StringParam),
        report=Grammar(None, StringParam),
        rule=Grammar(SnakeRule, KeywordSyntax),
        checkpoint=Grammar(SnakeRule, KeywordSyntax),
    )
