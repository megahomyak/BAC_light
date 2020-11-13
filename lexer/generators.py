from typing import Tuple, Callable

from lexer.enums import IntTypes
from lexer.lexer_classes import Command, Arg
from lexer.lexer_implementations import (
    VKPeerIDMetadataElement,
    VKSenderIDMetadataElement, IntArgType
)
from vk import vk_config


def get_getter_commands_for_common_orders(
        ru_names: Tuple[str, ...],
        eng_names: Tuple[str, ...],
        orders_name: str,  # Like "оплаченные заказы" ("paid orders")
        handler: Callable) -> Tuple[Command, Command, Command]:
    """
    Function, which will help to make repeating Commands, which are needed to
    get some orders.

    Args:
        ru_names: command's names on russian
        eng_names: command's names on english
        orders_name:
            which orders will be sent (like "оплаченные заказы" ("paid orders"
            on russian))
        handler:
            function, which will be called, when a command is entered. It should
            have such arguments: (client_vk_id: int, current_chat_peer_id: int,
            limit: int) (last argument is changing in each returned command)

    Returns:
        three Commands. First with default limit, second without limit and third
        with the specified limit.
    """
    metadata = (VKSenderIDMetadataElement, VKPeerIDMetadataElement)
    return (
        Command(  # With default limit
            names=ru_names + eng_names,
            handler=handler,
            description=(
                f"показывает {orders_name} с лимитом в "
                f"{vk_config.DEFAULT_BIG_ORDER_SEQUENCES_LIMIT} заказов "
                f"(если спрашивает клиент - только заказы этого же клиента)"
            ),
            metadata=metadata,
            fillers=(vk_config.DEFAULT_BIG_ORDER_SEQUENCES_LIMIT,)  # limit=
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
