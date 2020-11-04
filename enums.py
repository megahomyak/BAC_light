from enum import Enum, auto


class DBSessionChanged(Enum):

    NO = auto()
    MAYBE = auto()
    YES = auto()
