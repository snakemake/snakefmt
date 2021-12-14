class InvalidPython(Exception):
    pass


class StopParsing(Exception):
    pass


class EmptyContextError(Exception):
    pass


def NotAnIdentifierError(line_nb: str, identifier: str, keyword_line: str):
    raise SyntaxError(
        f"{line_nb}'{identifier}' in '{keyword_line}' is not a valid identifier"
    )


def ColonError(line_nb: str, identifier: str, keyword_line: str):
    raise SyntaxError(
        f"{line_nb}Colon (not '{identifier}') expected after " f"'{keyword_line}'"
    )


def NewlineError(line_nb: str, keyword_line: str):
    raise SyntaxError((f"{line_nb}Newline expected after keyword " f"'{keyword_line}'"))


def SyntaxFormError(line_nb: str, keyword_line: str, syntax_form: str):
    raise SyntaxError(f"{line_nb}'{keyword_line}' not of form '{syntax_form}'")


class InvalidParameterSyntax(Exception):
    pass


class InvalidParameter(Exception):
    pass


class NoParametersError(Exception):
    pass


class TooManyParameters(Exception):
    pass


class UnsupportedSyntax(Exception):
    pass


class InvalidBlackConfiguration(Exception):
    pass


class MalformattedToml(Exception):
    pass
