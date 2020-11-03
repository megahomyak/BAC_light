import re
from typing import Any, Tuple, Dict, List, Callable, Optional

from enums import GrammaticalCases
from lexer.lexer_classes import (
    Context, BaseArgType, BaseMetadataElement, Command,
    BaseConstantMetadataElement, ConstantContext
)


class IntArgType(BaseArgType):

    def __init__(self, is_signed: bool = True) -> None:
        self.is_signed = is_signed

    def _get_name(
            self, case: GrammaticalCases = GrammaticalCases.NOMINATIVE,
            singular: bool = True) -> str:
        if case is GrammaticalCases.NOMINATIVE:
            if singular:
                if self.is_signed:
                    return "целое число"
                return "положительное целое число"
            if self.is_signed:
                return "целые числа"
            return "положительные целые числа"
        elif case is GrammaticalCases.GENITIVE:
            if singular:
                if self.is_signed:
                    return "целого числа"
                return "положительного целого числа"
            if self.is_signed:
                return "целых чисел"
            return "положительных целых чисел"

    @property
    def regex(self) -> str:
        if self.is_signed:
            return r"-?\d+"
        return r"\d+"

    def convert(self, arg: str) -> int:
        return int(arg)


class MonthNumber(BaseArgType):

    def _get_name(
            self, case: GrammaticalCases = GrammaticalCases.NOMINATIVE,
            singular: bool = True) -> str:
        if case is GrammaticalCases.NOMINATIVE:
            if singular:
                return "номер месяца"
            return "номера месяцев"
        elif case is GrammaticalCases.GENITIVE:
            if singular:
                return "номера месяца"
            return "номеров месяцев"

    @property
    def regex(self) -> str:
        return r"(?:0?[1-9]|1[012])"

    def convert(self, arg: str) -> int:
        return int(arg)

    @property
    def description(self) -> str:
        return "число от 1 до 12 (еще можно писать 04 и аналогичное)"


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


class CommandsMetadataElement(BaseConstantMetadataElement):

    @staticmethod
    def get_data_from_constant_context(
            constant_context: ConstantContext) -> Tuple[Command, ...]:
        return constant_context.commands


class CommandDescriptionsMetadataElement(BaseConstantMetadataElement):

    @staticmethod
    def get_data_from_constant_context(
            constant_context: ConstantContext) -> Dict[str, List[Callable]]:
        return constant_context.command_descriptions


class CurrentYearMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> int:
        return context.current_datetime.year


class CurrentMonthMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> int:
        return context.current_datetime.month
