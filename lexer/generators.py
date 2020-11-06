from dataclasses import dataclass
from typing import Tuple, Callable

from lexer.lexer_classes import Command, Arg
from lexer.lexer_implementations import (
    VKPeerIDMetadataElement,
    VKSenderIDMetadataElement, IntArgType
)
from vk import vk_constants


@dataclass
class GetterCommandGenerator:

    """
    A class, objects of which is used to make three Commands to get some orders.
    """

    ru_names: Tuple[str, ...]
    eng_names: Tuple[str, ...]
    orders_name: str  # Like "оплаченные заказы" ("paid orders")
    handler: Callable

    def to_commands(self) -> Tuple[Command, Command, Command]:
        metadata = (
            VKSenderIDMetadataElement,
            VKPeerIDMetadataElement
        )
        return (
            Command(  # With default limit
                self.ru_names + self.eng_names,
                self.handler,
                (
                    f"показывает {self.orders_name} с лимитом в "
                    f"{vk_constants.DEFAULT_BIG_ORDER_SEQUENCES_LIMIT} заказов "
                    f"(если спрашивает клиент - только заказы этого же клиента)"
                ),
                metadata,
                (),
                (vk_constants.DEFAULT_BIG_ORDER_SEQUENCES_LIMIT,)  # limit=
            ),
            Command(  # Without limit
                (
                        tuple(f"все {name}" for name in self.ru_names)
                        +
                        tuple(f"all {name}" for name in self.eng_names)
                ),
                self.handler,
                (
                    f"показывает все {self.orders_name} (если спрашивает "
                    f"клиент - только заказы этого же клиента)"
                ),
                metadata,
                (),
                (None,)  # limit=
            ),
            Command(  # With the specified limit
                self.ru_names + self.eng_names,
                self.handler,
                (
                    f"показывает {self.orders_name} с указанным лимитом (если "
                    f"спрашивает клиент - только заказы этого же клиента)"
                ),
                metadata,
                (),
                (),
                (
                    Arg(
                        "лимит выдачи",
                        IntArgType(is_signed=False),
                        "сколько максимум описаний заказов будет отправлено"
                    ),
                )  # limit= (specified in argument)
            )
        )
