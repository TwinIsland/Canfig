from enum import Enum, auto


class TokenType(Enum):
    VERSION = auto()
    MIN_SUP = auto()
    AUTHOR = auto()
    DESCRIPTION = auto()
    LOG = auto()
    DOC = auto()
    HELP = auto()
    SEMI = auto()
    STRING = auto()
    IDENT = auto()
    LCBRACE = auto()
    RCBRACE = auto()
    STRUCT = auto()
    SLICE = auto()
    TRIGGER = auto()
    TRICOND = auto()
    PYARG = auto()
    LPAREN = auto()
    RPAREN = auto()
    CONFIG = auto()
    COMMAND = auto()
    ARGUMENT = auto()
    EOF = auto()


class TagTokenType(Enum):
    VERSION = auto()
    MIN_SUP = auto()
    AUTHOR = auto()
    DESCRIPTION = auto()
    LOG = auto()
    DOC = auto()
    HELP = auto()


class Token:
    def __init__(self, type, value=None):
        if type in [
            TokenType.STRING,
            TokenType.IDENT,
            TokenType.COMMAND,
            TokenType.ARGUMENT,
        ] and not isinstance(value, str):
            raise ValueError("This token type requires a string value")
        self.type = type
        self.value = value

    def __str__(self):
        if self.value is not None:
            return f"{self.type.name}({self.value})"
        return self.type.name
