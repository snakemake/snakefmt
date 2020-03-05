from typing import Tuple
from .syntax import (
    namedtuple,
    KeywordSyntax,
    ParamList,
    ParamSingle,
    StringParamSingle,
    NumericParamSingle,
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
        threads=Grammar(None, NumericParamSingle),
        resources=Grammar(None, ParamList),
        priority=Grammar(None, NumericParamSingle),
        version=Grammar(None, ParamSingle),
        log=Grammar(None, ParamList),
        message=Grammar(None, StringParamSingle),
    )


class SnakeGlobal(Language):
    spec = dict(
        include=Grammar(None, StringParamSingle),
        workdir=Grammar(None, StringParamSingle),
        configfile=Grammar(None, StringParamSingle),
        report=Grammar(None, StringParamSingle),
        rule=Grammar(SnakeRule, KeywordSyntax),
        checkpoint=Grammar(SnakeRule, KeywordSyntax),
    )
