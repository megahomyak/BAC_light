import asyncio
import traceback
from typing import NoReturn, Optional, List, Tuple, Dict, Callable

import aiohttp
import simplest_logger
from simple_avk import SimpleAVK

import exceptions
from enums import DBSessionChanged
from handlers.handler_helpers import HandlerHelpers
from handlers.handlers import Handlers, HandlingResult
from lexer.lexer_classes import Command, Arg, Context, ConstantContext
from lexer.lexer_implementations import (
    StringArgType, VKSenderIDMetadataElement, VKPeerIDMetadataElement,
    SequenceArgType, IntArgType, CommandsMetadataElement,
    CommandDescriptionsMetadataElement
)
from orm import db_apis
from vk import vk_constants
from vk.vk_related_classes import Message
from vk.vk_worker import VKWorker


class MainLogic:

    def __init__(
            self, managers_containter: db_apis.ManagersContainer,
            vk_worker: VKWorker, handlers: Handlers,
            logger: Optional[simplest_logger.Logger] = None,
            log_command_parsing_errors: bool = True) -> None:
        self.managers_containter = managers_containter
        self.vk_worker = vk_worker
        self.logger = logger
        self.log_command_parsing_errors = log_command_parsing_errors
        self.commands: Tuple[Command, ...] = (
            Command(
                ("заказ", "order", "заказать"),
                handlers.create_order,
                "создает новый заказ",
                (
                    VKSenderIDMetadataElement,
                ),
                (),
                (
                    Arg(
                        "текст заказа",
                        StringArgType()
                    ),
                )
            ),
            Command(
                ("отменить", "отмена", "cancel"),
                handlers.cancel_orders,
                (
                    "отменяет заказ (клиентам нельзя отменять чужие заказы; "
                    "сотрудникам нельзя отменять заказы, взятые другим "
                    "сотрудником; всем нельзя отменять оплаченные заказы)"
                ),
                (
                    VKSenderIDMetadataElement,
                    VKPeerIDMetadataElement
                ),
                (),
                (
                    Arg(
                        "ID заказов, которые нужно отменить (через запятую)",
                        SequenceArgType(
                            IntArgType()
                        )
                    ),
                    Arg(
                        "причина отмены",
                        StringArgType()
                    )
                )
            ),
            Command(
                ("заказы", "orders"),
                handlers.get_orders,
                (
                    "показывает все заказы (если спрашивает клиент - "
                    "только заказы этого же клиента)"
                ),
                (
                    VKSenderIDMetadataElement,
                    VKPeerIDMetadataElement
                )
            ),
            Command(
                ("взятые", "взятые заказы", "taken", "taken orders"),
                handlers.get_taken_orders,
                (
                    "показывает все взятые заказы, которые не отменены и не "
                    "оплачены (если спрашивает клиент - только заказы этого же "
                    "клиента)"
                ),
                (
                    VKSenderIDMetadataElement,
                    VKPeerIDMetadataElement
                )
            ),
            Command(
                ("в ожидании", "waiting", "pending", "ожидающие"),
                handlers.get_pending_orders,
                (
                    "показывает все заказы, которые еще не взяты и не отменены "
                    "(если спрашивает клиент - только заказы этого же "
                    "клиента)"
                ),
                (
                    VKSenderIDMetadataElement,
                    VKPeerIDMetadataElement
                )
            ),
            Command(
                ("команды", "помощь", "help", "commands"),
                handlers.get_help_message,
                "показывает помощь по командам и их написанию",
                (),
                (
                    CommandsMetadataElement,
                )
            ),
            Command(
                ("отмененные", "canceled"),
                handlers.get_canceled_orders,
                (
                    "показывает все отмененные заказы (если спрашивает клиент "
                    "- только заказы этого же клиента)"
                ),
                (
                    VKSenderIDMetadataElement,
                    VKPeerIDMetadataElement
                )
            ),
            Command(
                ("оплаченные", "paid"),
                handlers.get_paid_orders,
                (
                    "показывает все оплаченные заказы (если спрашивает клиент "
                    "- только заказы этого же клиента)"
                ),
                (
                    VKSenderIDMetadataElement,
                    VKPeerIDMetadataElement
                )
            ),
            Command(
                ("оплачено", "оплатить", "pay", "mark as paid"),
                handlers.mark_orders_as_paid,
                (
                    "отмечает заказ оплаченным (это могут делать только "
                    "сотрудники, причем могут помечать оплаченными лишь те "
                    "заказы, которые взяли сами)"
                ),
                (
                    VKSenderIDMetadataElement,
                    VKPeerIDMetadataElement
                ),
                (),
                (
                    Arg(
                        (
                            "ID заказов, которые нужно отметить оплаченными "
                            "(через запятую)"
                        ),
                        SequenceArgType(
                            IntArgType()
                        )
                    ),
                    Arg(
                        "выручка (с каждого указанного заказа)",
                        IntArgType(is_signed=False)
                    )
                )
            ),
            Command(
                ("месячное", "monthly"),
                handlers.get_monthly_paid_orders,
                (
                    "показывает оплаченные заказы за месяц (только для "
                    "сотрудников)"
                ),
                (
                    VKPeerIDMetadataElement,
                )
            ),
            Command(
                ("месячное", "monthly"),
                handlers.get_monthly_paid_orders_by_month_and_year,
                (
                    "показывает оплаченные заказы за указанный месяц "
                    "указанного года (только для сотрудников)"
                ),
                (
                    VKPeerIDMetadataElement,
                ),
                (),
                (
                    Arg(
                        "номер месяца",
                        IntArgType()
                    ),
                    Arg(
                        "номер года",
                        IntArgType()
                    )
                )
            ),
            Command(
                ("месячное", "monthly"),
                handlers.get_monthly_paid_orders_by_month,
                (
                    "показывает оплаченные заказы за указанный месяц (только "
                    "для сотрудников)"
                ),
                (
                    VKPeerIDMetadataElement,
                ),
                (),
                (
                    Arg(
                        "номер месяца",
                        IntArgType()
                    ),
                )
            ),
            Command(
                ("взять", "take"),
                handlers.take_orders,
                (
                    "отмечает заказы как взятые и отсылает уведомления о "
                    "взятии клиентам (только для сотрудников)"
                ),
                (
                    VKPeerIDMetadataElement,
                    VKSenderIDMetadataElement
                ),
                (),
                (
                    Arg(
                        (
                            "ID заказов, которые нужно отметить "
                            "взятыми (через запятую)"
                        ),
                        SequenceArgType(
                            IntArgType()
                        )
                    ),
                )
            ),
            Command(
                ("активные", "active"),
                handlers.get_active_orders,
                (
                    "показывает все заказы, которые не отменены и не оплачены "
                    "(если спрашивает клиент - только заказы этого же клиента)"
                ),
                (
                    VKSenderIDMetadataElement,
                    VKPeerIDMetadataElement
                )
            ),
            Command(
                ("команды", "помощь", "help", "commands"),
                handlers.get_help_message_for_specific_commands,
                "показывает помощь по конкретным командам и их написанию",
                (),
                (
                    CommandDescriptionsMetadataElement,
                ),
                (
                    Arg(
                        (
                            "команды, к которым нужно получить подсказку "
                            "(через запятую)"
                        ),
                        SequenceArgType(
                            StringArgType()
                        )
                    ),
                )
            ),
            Command(
                ("инфо", "info", "information", "информация"),
                handlers.get_order_by_id,
                (
                    "показывает заказы с указанными ID (для клиентов - лишь "
                    "если заказ принадлежит им)"
                ),
                (
                    VKSenderIDMetadataElement,
                    VKPeerIDMetadataElement
                ),
                (),
                (
                    Arg(
                        "ID заказов (через запятую)",
                        SequenceArgType(
                            IntArgType()
                        )
                    ),
                )
            )
        )
        self.commands_description: Dict[str, List[Callable]] = {}
        for command in self.commands:
            for name in command.names:
                try:
                    self.commands_description[name].append(
                        command.get_full_description
                    )
                except KeyError:
                    self.commands_description[name] = [
                        command.get_full_description
                    ]

    async def handle_command(
            self, vk_message_info: dict,
            constant_context: ConstantContext) -> List[Message]:
        command = vk_message_info["text"][1:]  # Cutting /
        current_chat_peer_id = vk_message_info["peer_id"]
        error_args_amount = 0
        for command_ in self.commands:
            try:
                args = command_.convert_command_to_args(command)
            except exceptions.ParsingError as parsing_error:
                if parsing_error.args_num > error_args_amount:
                    error_args_amount = parsing_error.args_num
            else:
                context = Context(vk_message_info)
                handling_result: HandlingResult = await command_.handler(
                    *command_.get_converted_metadata(context),
                    *command_.get_converted_constant_metadata(constant_context),
                    *args
                )
                if handling_result.db_changes is DBSessionChanged.YES:
                    self.managers_containter.commit()
                elif handling_result.db_changes is DBSessionChanged.MAYBE:
                    self.managers_containter.commit_if_something_is_changed()
                return handling_result.notification.to_messages(
                    client_peer_id=current_chat_peer_id
                )
        if error_args_amount == 0:
            error_msg = "Ошибка обработки команды на её названии!"
        else:
            error_msg = (
                f"Ошибка обработки команды на аргументе номер "
                f"{error_args_amount} (он неправильный или пропущен)"
            )
        if self.logger is not None and self.log_command_parsing_errors:
            from_id = vk_message_info['from_id']
            chat_name = (
                "чате для сотрудников"
                if (
                    current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID
                ) else
                "ЛС"
            )
            if error_args_amount == 0:
                self.logger.info(
                    f"Ошибка обработки команды \"{command}\" от пользователя с "
                    f"VK ID {from_id} в {chat_name} на её названии!"
                )
            else:
                self.logger.info(
                    f"Ошибка обработки команды \"{command}\" от пользователя с "
                    f"VK ID {from_id} в {chat_name} на аргументе номер "
                    f"{error_args_amount} (он неправильный или пропущен)"
                )
        return [
            Message(
                error_msg,
                current_chat_peer_id
            )
        ]

    async def reply_to_vk_message(
            self, message_info: dict,
            constant_context: ConstantContext) -> None:
        await self.vk_worker.multiple_reply(
            *await self.handle_command(message_info, constant_context)
        )

    async def future_done_callback(
            self, peer_id: int, text: str,
            future: asyncio.Future) -> None:
        exc = future.exception()
        if exc:
            if self.logger is not None:
                chat_name = (
                    "чате для сотрудников"
                    if peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID else
                    "ЛС"
                )
                self.logger.error(
                    f"Ошибка на команде \"{text}\" в {chat_name}:\n" + "".join(
                        traceback.TracebackException.from_exception(
                            exc
                        ).format()
                    )
                )
            await self.vk_worker.multiple_reply(
                Message(
                    f"Тут у юзера при обработке команды \"{text}\" произошла "
                    f"ошибка \"{str(exc)}\", это в логах тоже есть, "
                    f"гляньте, разберитесь...",
                    vk_constants.EMPLOYEES_CHAT_PEER_ID
                )
            )
            if peer_id != vk_constants.EMPLOYEES_CHAT_PEER_ID:
                await self.vk_worker.multiple_reply(
                    Message(
                        f"При обработке команды \"{text}\" произошла ошибка. "
                        f"Она была залоггирована, админы - уведомлены.",
                        peer_id
                    )
                )

    async def listen_for_vk_events(self) -> NoReturn:
        constant_context = ConstantContext(
            self.commands,
            self.commands_description
        )
        async for message_info in self.vk_worker.listen_for_messages():
            text: str = message_info["text"]
            peer_id: int = message_info["peer_id"]
            if text.startswith("/"):
                text = text[1:]  # Cutting /
                asyncio.create_task(
                    self.reply_to_vk_message(message_info, constant_context)
                ).add_done_callback(
                    lambda future: asyncio.create_task(
                        self.future_done_callback(
                            peer_id, text, future
                        )
                    )
                )


async def main():
    async with aiohttp.ClientSession() as aiohttp_session:
        vk_worker = VKWorker(
            SimpleAVK(
                aiohttp_session,
                vk_constants.TOKEN,
                vk_constants.GROUP_ID
            ),
            simplest_logger.Logger("vk_info.log"),
            log_only_user_info_getting=True
        )
        db_session = db_apis.get_db_session("sqlite:///BAC_light.db")
        managers_containter = db_apis.ManagersContainer(
            db_apis.OrdersManager(db_session),
            db_apis.CachedVKUsersManager(db_session, vk_worker)
        )
        main_logic = MainLogic(
            managers_containter,
            vk_worker,
            Handlers(
                HandlerHelpers(managers_containter),
                managers_containter
            ),
            simplest_logger.Logger("command_errors.log"),
            log_command_parsing_errors=False
        )
        await main_logic.listen_for_vk_events()


if __name__ == "__main__":
    asyncio.run(main())
