from typing import Any

from lexer import lexer_classes
from lexer.lexer_classes import Context


class IntArgType(lexer_classes.BaseArgType):

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


class StringArgType(lexer_classes.BaseArgType):

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


class OrdersManagerMetadataElement(lexer_classes.BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: lexer_classes.Context) -> Any:
        return context.orders_manager


class VKSenderIDMetadataElement(lexer_classes.BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: lexer_classes.Context) -> Any:
        return context.vk_message_info["from_id"]


class VKWorkerMetadataElement(lexer_classes.BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: Context) -> Any:
        return context.vk_worker


class VKPeerIDMetadataElement(lexer_classes.BaseMetadataElement):

    @staticmethod
    def get_data_from_context(context: lexer_classes.Context) -> Any:
        return context.vk_message_info["peer_id"]
