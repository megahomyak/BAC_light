from enum import Enum


class GrammaticalCases(Enum):
    NOMINATIVE = "nom"
    GENITIVE = "gen"
    DATIVE = "dat"
    ACCUSATIVE = "acc"
    INSTRUMENTAL = "ins"
    PREPOSITIONAL = "abl"  # IDK why short name is abl in docs...
