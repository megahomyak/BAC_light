import re
from typing import Any, Tuple, Dict, List, Callable, Optional

from enums import GrammaticalCases
from lexer.lexer_classes import (
    Context, BaseArgType, BaseMetadataElement, Command
)


class IntArgType(BaseArgType):

    def _get_name(
            self, case: GrammaticalCases = GrammaticalCases.NOMINATIVE,
            singular: bool = True) -> str:
        if case is GrammaticalCases.NOMINATIVE:
            if singular:
                return "целое число"
            else:
                return "целые числа"
        elif case is GrammaticalCases.GENITIVE:
            if singular:
                return "целого числа"
            else:
                return "целых чисел"

    @property
    def name(self) -> str:
        return self.get_name()

    @property
    def regex(self) -> str:
        return r"-?\d+"

    def convert(self, arg: str) -> int:
        return int(arg)


class StringArgType(BaseArgType):

    def _get_name(
            self, case: GrammaticalCases = GrammaticalCases.NOMINATIVE,
            singular: bool = True) -> Optional[str]:
        string_word: Optional[str] = None
        if case is GrammaticalCases.NOMINATIVE:
            if singular:
                string_word = "строка"
            else:
                string_word = "строки"
        elif case is GrammaticalCases.GENITIVE:
            if singular:
                string_word = "строки"
            else:
                string_word = "строк"
        if string_word is not None:
            if self.length_limit is None:
                return string_word
            return f"{string_word} с лимитом {self.length_limit}"

    @property
    def regex(self) -> str:
        if self.length_limit is None:
            return r".+?"
        return fr"(?:.+?){{1,{self.length_limit}}}"

    def __init__(self, length_limit: int = None) -> None:
        self.length_limit = length_limit

    def convert(self, arg: str) -> str:
        return arg


class SequenceArgType(BaseArgType):

    def _get_name(
            self, case: GrammaticalCases = GrammaticalCases.NOMINATIVE,
            singular: bool = True) -> str:
        sequence_word: Optional[str] = None
        if case is GrammaticalCases.NOMINATIVE:
            if singular:
                sequence_word = "последовательность"
            else:
                sequence_word = "последовательности"
        elif case is GrammaticalCases.GENITIVE:
            if singular:
                sequence_word = "последовательности"
            else:
                sequence_word = "последовательностей"
        if sequence_word is not None:
            element_name = self.element_type.get_name(
                GrammaticalCases.GENITIVE,
                singular=False
            )
            return f"{sequence_word} {element_name}"

    @property
    def regex(self) -> str:
        return (
            f"{self.element_type.regex}"
            f"(?:{self.separator}{self.element_type.regex})*"
        )

    @property
    def description(self) -> str:
        return (
            f"От 1 до бесконечности элементов типа '{self.element_type.name}', "
            f"разделенных через '{self.separator}' (<- регулярное выражение)"
        )

    def __init__(
            self, element_type: BaseArgType, separator: str = r" *, *") -> None:
        self.element_type = element_type
        self.separator = separator

    def convert(self, arg: str) -> Tuple[Any, ...]:
        return tuple(
            self.element_type.convert(element)
            for element in re.split(self.separator, arg)
        )


class VKSenderIDMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> int:
        return context.vk_message_info["from_id"]


class VKPeerIDMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> int:
        return context.vk_message_info["peer_id"]


class CommandsMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> Tuple[Command, ...]:
        return context.commands


class CommandDescriptionsMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> Dict[str, List[Callable]]:
        return context.command_descriptions
