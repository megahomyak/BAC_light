import asyncio
import traceback
from typing import NoReturn

import aiohttp
import pysimplelog

import exceptions
from handlers.handler_helpers import HandlerHelpers
from handlers.handlers import Handlers
from lexer.lexer_classes import Command, Arg, Context
from lexer.lexer_implementations import (
    StringArgType, VKSenderIDMetadataElement, VKPeerIDMetadataElement,
    SequenceArgType, IntArgType, CommandsMetadataElement
)
from orm import db_apis
from vk import vk_constants
from vk.dataclasses_ import Notification, Message, NotificationTexts
from vk.vk_worker import VKWorker


class MainLogic:

    def __init__(
            self, vk_worker: VKWorker,
            orders_manager: db_apis.OrdersManager,
            logger: pysimplelog.Logger,
            handlers: Handlers) -> None:
        self.vk_worker = vk_worker
        self.orders_manager = orders_manager
        self.logger = logger
        self.commands = (
            Command(
                ("заказ", "order", "заказать"),
                handlers.create_order,
                "создает новый заказ",
                (
                    VKSenderIDMetadataElement,
                ),
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
                "показывает помощь по командам",
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
                handlers.make_orders_paid,
                (
                    "отмечает заказ оплаченным (это могут делать только "
                    "сотрудники, причем могут помечать оплаченными лишь те "
                    "заказы, которые взяли сами)"
                ),
                (
                    VKSenderIDMetadataElement,
                    VKPeerIDMetadataElement
                ),
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
                        IntArgType()
                    )
                )
            ),
        )

    async def handle_command(
            self, vk_message_info: dict) -> Notification:
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
                context = Context(
                    vk_message_info,
                    self.commands
                )
                notification_texts: NotificationTexts = await command_.handler(
                    *command_.get_converted_metadata(context),
                    *args
                )
                return notification_texts.to_notification(
                    employees_chat_peer_id=vk_constants.EMPLOYEES_CHAT_PEER_ID,
                    client_chat_peer_id=current_chat_peer_id
                )
        if error_args_amount == 0:
            error_msg = "Ошибка обработки команды на её названии!"
        else:
            error_msg = (
                f"Ошибка обработки команды на аргументе номер "
                f"{error_args_amount} (он неправильный или пропущен)"
            )
        return Notification(
            message_for_client=Message(
                error_msg,
                current_chat_peer_id
            )
        )

    async def reply_to_vk_message(self, message_info: dict) -> None:
        await self.vk_worker.send_notifications(
            await self.handle_command(message_info)
        )

    async def future_done_callback(
            self, peer_id: int, text: str,
            future: asyncio.Future) -> None:
        exc = future.exception()
        if exc:
            self.logger.error(
                "".join(
                    traceback.TracebackException.from_exception(exc).format()
                )
            )
            await self.vk_worker.reply(
                Message(
                    f"Тут у юзера при обработке команды \"{text}\" произошла "
                    f"ошибка \"{str(exc)}\", это в логах тоже есть, "
                    f"гляньте, разберитесь...",
                    vk_constants.EMPLOYEES_CHAT_PEER_ID
                )
            )
            if peer_id != vk_constants.EMPLOYEES_CHAT_PEER_ID:
                await self.vk_worker.reply(
                    Message(
                        f"При обработке команды \"{text}\" произошла ошибка. "
                        f"Она была залоггирована, админы - уведомлены.",
                        peer_id
                    )
                )

    async def listen_for_vk_events(self) -> NoReturn:
        async for event in self.vk_worker.listen():
            if event["type"] == "message_new":
                message_info = event["object"]["message"]
                text: str = message_info["text"]
                peer_id: int = message_info["peer_id"]
                print(f"{peer_id=}; {text=}")
                if text.startswith("/"):
                    text = text[1:]  # Cutting /
                    asyncio.create_task(
                        self.reply_to_vk_message(message_info)
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
            aiohttp_session,
            vk_constants.TOKEN,
            vk_constants.GROUP_ID
        )
        sqlalchemy_session = db_apis.get_sqlalchemy_db_session(
            "sqlite:///BAC_light.db"
        )
        orders_manager = db_apis.OrdersManager(
            sqlalchemy_session
        )
        users_manager = db_apis.VKUsersManager(
            sqlalchemy_session, vk_worker
        )
        main_logic = MainLogic(
            vk_worker,
            orders_manager,
            pysimplelog.Logger(
                "command_errors",
                logFileBasename="command_errors",
                logFileMaxSize=None,
                logFileFirstNumber=None
            ),
            Handlers(
                vk_worker,
                orders_manager,
                HandlerHelpers(
                    vk_worker,
                    users_manager
                ),
                users_manager
            )
        )
        await main_logic.listen_for_vk_events()


if __name__ == "__main__":
    asyncio.run(main())
