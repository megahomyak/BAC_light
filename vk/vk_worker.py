import asyncio
import random
from typing import AsyncGenerator, Optional, Any

import simplest_logger
from simple_avk import SimpleAVK

from vk import vk_constants
from vk.dataclasses_ import Message
from vk.enums import NameCases, Sex


class VKWorker:

    def __init__(
            self, simple_avk: SimpleAVK,
            logger: Optional[simplest_logger.Logger] = None,
            log_only_user_info_getting: bool = False) -> None:
        self.vk = simple_avk
        self.logger = logger
        self.log_only_user_info_getting = log_only_user_info_getting

    async def listen_for_messages(self) -> AsyncGenerator[Any, None]:
        async for event in self.vk.listen():
            if event["type"] == "message_new":
                message_info = event["object"]["message"]
                if (
                    self.logger is not None
                    and
                    not self.log_only_user_info_getting
                ):
                    self.logger.info(
                        f"Новое сообщение из чата с peer_id "
                        f"{message_info['peer_id']}: {message_info['text']}"
                    )
                yield message_info

    async def reply(self, message: Message) -> None:
        text_parts = (
            message.text[i:i + vk_constants.SYMBOLS_PER_MESSAGE]
            for i in range(
                0,
                len(message.text),
                vk_constants.SYMBOLS_PER_MESSAGE
            )
        )
        for part in text_parts:
            await self.vk.call_method(
                "messages.send",
                {
                    "peer_id": message.peer_id,
                    "message": part,
                    "random_id": random.randint(-1_000_000, 1_000_000),
                    "disable_mentions": 1
                }
            )
        if (
            self.logger is not None
            and
            not self.log_only_user_info_getting
        ):
            self.logger.info(
                f"Отправлено сообщение в чат с peer_id {message.peer_id}: "
                f"{message.text}"
            )

    async def multiple_reply(self, *messages: Message) -> None:
        await asyncio.gather(
            *(
                self.reply(message)
                for message in messages
            )
        )

    async def get_user_info(
            self, user_vk_id: int,
            name_case: NameCases = NameCases.NOM) -> dict:
        if self.logger is not None:
            self.logger.info(
                f"Запрос информации о пользователе с VK ID {user_vk_id} с "
                f"падежом имени и фамилии {name_case.value}"
            )
        user_info = await self.vk.call_method(
            "users.get",
            {
                "user_ids": user_vk_id,
                "fields": "sex",
                "name_case": name_case.value
            }
        )
        user_info = user_info[0]
        user_info["sex"] = Sex.FEMALE if user_info["sex"] == 1 else Sex.MALE
        return user_info
