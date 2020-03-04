from typing import Tuple
from .syntax import namedtuple, ParamList, ParamSingle, KeywordSyntax


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
    spec = dict(input=Grammar(None, ParamList), output=Grammar(None, ParamList))


class SnakeGlobal(Language):
    spec = dict(rule=Grammar(SnakeRule, KeywordSyntax))
