class DuplicateKeyWordError(Exception):
    pass


class InvalidSyntax(Exception):
    pass


class StopParsing(Exception):
    pass


class UnrecognisedKeyword(Exception):
    pass


class EmptyContextError(Exception):
    pass
