import asyncio
import logging
import random
from typing import AsyncGenerator, Optional, Any, Union, List

from simple_avk import SimpleAVK

from enums import GrammaticalCases
from vk import vk_related_classes
from vk.enums import Sex
from vk.vk_config import VkConfig
from vk.vk_related_classes import Message, DoneReply


class VKWorker:

    def __init__(
            self, simple_avk: SimpleAVK, vk_config: VkConfig,
            logger: Optional[logging.Logger] = None):
        self.vk = simple_avk
        self.logger = logger
        self.vk_config = vk_config

    async def listen_for_messages(self) -> AsyncGenerator[Any, None]:
        async for event in self.vk.listen():
            if event["type"] == "message_new":
                message_info = event["object"]["message"]
                if self.logger is not None:
                    self.logger.debug(
                        f"Новое сообщение из чата с peer_id "
                        f"{message_info['peer_id']}: {message_info['text']}"
                    )
                yield message_info

    async def reply(self, message: Message) -> None:
        text_parts = (
            message.text[i:i + self.vk_config.SYMBOLS_PER_MESSAGE]
            for i in range(
                0,
                len(message.text),
                self.vk_config.SYMBOLS_PER_MESSAGE
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
        if self.logger is not None:
            self.logger.debug(
                f"Отправлено сообщение в чат с peer_id {message.peer_id}: "
                f"{message.text}"
            )

    async def multiple_reply(self, messages: List[Message]) -> List[DoneReply]:
        exceptions = await asyncio.gather(
            *(self.reply(message) for message in messages),
            return_exceptions=True
        )
        return [
            DoneReply(exception, message)
            for message, exception in zip(messages, exceptions)
        ]

    async def get_user_info(
            self, user_vk_id: Union[int, str],
            name_case: GrammaticalCases = GrammaticalCases.NOMINATIVE
            ) -> vk_related_classes.VKUserInfo:
        """
        Gets info about VK user from VK.

        Warnings:
            The sex field contains a Sex enum, not exactly a value received from
            VK!

        Args:
            user_vk_id: id of a VK user
            name_case: element of enums.GrammaticalCases

        Returns:
            slightly changed (check Warnings) first element of a json, which is
            received from VK
        """
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
        return vk_related_classes.VKUserInfo(
            user_info["id"],
            user_info["first_name"],
            user_info["last_name"],
            Sex.FEMALE if user_info["sex"] == 1 else Sex.MALE
        )
