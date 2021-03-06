from typing import Tuple, Callable, Awaitable

from handlers.dataclasses import HandlingResult
from lexer.enums import IntTypes
from lexer.lexer_classes import Command, Arg
from lexer.lexer_implementations import (
    VKPeerIDGetter,
    VKSenderIDGetter, IntArgType
)
from vk.vk_config import VkConfig


class CommandsGenerator:

    def __init__(self, vk_config: VkConfig):
        self.vk_config = vk_config

    def get_getter_commands_for_common_orders(
            self, ru_names: Tuple[str, ...], eng_names: Tuple[str, ...],
            orders_name: str,  # Like "оплаченные заказы" ("paid orders")
            handler: Callable[..., Awaitable[HandlingResult]]
            ) -> Tuple[Command, Command, Command]:
        """
        Function, which will help to make repeating Commands, which are needed
        to get some orders.

        Args:
            ru_names: command's names on russian
            eng_names: command's names on english
            orders_name:
                which orders will be sent (like "оплаченные заказы" ("paid
                orders" in russian))
            handler:
                function, which will be called, when a command is entered. It
                should have such arguments: (client_vk_id: int,
                current_chat_peer_id: int, limit: int)
                (last argument is changing in each returned command)

        Returns:
            three Commands. First with default limit, second without limit and
            third with the specified limit.
        """
        metadata = (VKSenderIDGetter, VKPeerIDGetter)
        return (
            Command(  # With default limit
                names=ru_names + eng_names,
                handler=handler,
                description=(
                    f"показывает {orders_name} с лимитом в "
                    f"{self.vk_config.DEFAULT_BIG_ORDER_SEQUENCES_LIMIT} "
                    f"заказов (если спрашивает клиент - только заказы этого же "
                    f"клиента)"
                ),
                metadata=metadata,
                # limit=self.vk_config.DEFAULT_BIG_ORDER_SEQUENCES_LIMIT
                fillers=(self.vk_config.DEFAULT_BIG_ORDER_SEQUENCES_LIMIT,)
            ),
            Command(  # Without limit
                names=(
                    tuple(f"все {name}" for name in ru_names) +
                    tuple(f"all {name}" for name in eng_names)
                ),
                handler=handler,
                description=(
                    f"показывает все {orders_name} (если спрашивает "
                    f"клиент - только заказы этого же клиента)"
                ),
                metadata=metadata,
                fillers=(None,)  # limit=
            ),
            Command(  # With the specified limit
                names=ru_names + eng_names,
                handler=handler,
                description=(
                    f"показывает {orders_name} с указанным лимитом (если "
                    f"спрашивает клиент - только заказы этого же клиента)"
                ),
                metadata=metadata,
                arguments=(
                    Arg(
                        "лимит выдачи",
                        IntArgType(IntTypes.GREATER_THAN_ZERO),
                        "сколько максимум описаний заказов будет отправлено"
                    ),  # limit= (specified by user)
                )
            )
        )
