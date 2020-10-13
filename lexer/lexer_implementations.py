import re
from typing import Any, Tuple

from lexer.lexer_classes import Context, BaseArgType, BaseMetadataElement


class IntArgType(BaseArgType):

    @property
    def name(self) -> str:
        if self.is_signed:
            return "целое число"
        return "неотрицательное целое число"

    @property
    def regex(self) -> str:
        if self.is_signed:
            return r"-?\d+"
        return r"\d+"

    def __init__(self, is_signed: bool = True) -> None:
        self.is_signed = is_signed

    def convert(self, arg: str) -> int:
        return int(arg)


class StringArgType(BaseArgType):

    @property
    def name(self) -> str:
        if self.length_limit is None:
            return "строка"
        return f"строка с лимитом {self.length_limit}"

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

    @property
    def name(self) -> str:
        return f"последовательность <{self.element_type.name}>"

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

    def convert(self, arg: str) -> Tuple[Any]:
        return tuple(
            self.element_type.convert(element)
            for element in re.split(self.separator, arg)
        )


class OrdersManagerMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> Any:
        return context.orders_manager


class VKSenderIDMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> Any:
        return context.vk_message_info["from_id"]


class VKWorkerMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> Any:
        return context.vk_worker


class VKPeerIDMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> Any:
        return context.vk_message_info["peer_id"]


class EmployeesChatPeerIDMetadataElement(BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> Any:
        return context.employees_chat_peer_id
