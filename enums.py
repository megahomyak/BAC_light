from enum import Enum, auto


class Sex(Enum):

    MALE = 2
    FEMALE = 1


class DBSessionChanged(Enum):

    NO = auto()
    MAYBE = auto()
    YES = auto()
