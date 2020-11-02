from enum import Enum, auto


class Sex(Enum):

    MALE = 2
    FEMALE = 1


class GrammaticalCases(Enum):

    NOMINATIVE = "nom"
    GENITIVE = "gen"
    DATIVE = "dat"
    ACCUSATIVE = "acc"
    INSTRUMENTAL = "ins"
    PREPOSITIONAL = "abl"  # IDK why short name is abl in docs...


class DBSessionChanged(Enum):

    NO = auto()
    MAYBE = auto()
    YES = auto()
