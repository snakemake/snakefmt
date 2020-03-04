class DuplicateKeyWordError(Exception):
    pass


class StopParsing(Exception):
    pass


class EmptyContextError(Exception):
    pass


class InvalidParameterSyntax(Exception):
    pass


class InvalidParameter(Exception):
    pass


class NoParametersError(Exception):
    pass


class TooManyParameters(Exception):
    pass
