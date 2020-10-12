import asyncio
from typing import NoReturn

import aiohttp
import pysimplelog

import handlers
from lexer.lexer_classes import Command, Arg, ParsingError, Context
from lexer.lexer_implementations import (
    StringArgType, OrdersManagerMetadataElement, VKSenderIDMetadataElement,
    VKWorkerMetadataElement, EmployeesChatPeerIDMetadataElement
)
from orm import db_apis
from vk import vk_constants
from vk.message_classes import Notification, Message
from vk.vk_worker import VKWorker


class MainLogic:

    def __init__(
            self, vk_worker: VKWorker,
            orders_manager: db_apis.OrdersManager,
            logger: pysimplelog.Logger) -> None:
        self.vk_worker = vk_worker
        self.orders_manager = orders_manager
        self.logger = logger
        self.commands = (
            Command(
                ("заказ", "order", "заказать"),
                handlers.create_order,
                "создает новый заказ и отсылает уведомление сотрудникам",
                (
                    OrdersManagerMetadataElement,
                    VKWorkerMetadataElement,
                    VKSenderIDMetadataElement,
                    EmployeesChatPeerIDMetadataElement
                ),
                (
                    Arg(
                        "текст заказа",
                        StringArgType()
                    ),
                )
            ),
        )

    async def handle_command(
            self, vk_message_info: dict) -> Notification:
        command = vk_message_info["text"][1:]  # Cutting /
        for command_ in self.commands:
            try:
                args = command_.convert_command_to_args(command)
            except ParsingError:
                pass
            else:
                context = Context(
                    self.orders_manager,
                    self.vk_worker,
                    vk_message_info,
                    vk_constants.EMPLOYEES_CHAT_PEER_ID
                )
                return await command_.handler(
                    *command_.get_converted_metadata(context),
                    *args
                )
        return Notification(
            message_for_client=Message(
                "Что?",
                vk_message_info["peer_id"]
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
            self.logger.error(str(exc))
            await self.vk_worker.reply(
                Message(
                    f"Тут у юзера при обработке команды \"{text}\" произошла "
                    f"ошибка \"{str(exc)}\", это в логах тоже есть, гляньте, "
                    f"разберитесь...",
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
        main_logic = MainLogic(
            VKWorker(
                aiohttp_session,
                vk_constants.TOKEN,
                vk_constants.GROUP_ID
            ),
            db_apis.OrdersManager(
                db_apis.get_sqlalchemy_db_session("sqlite:///BAC_light.db")
            ),
            pysimplelog.Logger(
                "command_errors",
                logFileBasename="command_errors",
                logFileMaxSize=None,
                logFileFirstNumber=None
            )
        )
        await main_logic.listen_for_vk_events()


if __name__ == "__main__":
    asyncio.run(main())
