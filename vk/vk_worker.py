import random
from typing import Optional

import aiohttp
from simple_avk import SimpleAVK

from vk.message_classes import Notification, Message


class VKWorker(SimpleAVK):

    def __init__(
            self, aiohttp_session: aiohttp.ClientSession,
            message_symbols_limit: Optional[int] = 4096) -> None:
        super().__init__(aiohttp_session)
        self.message_symbols_limit = message_symbols_limit

    async def reply(self, *messages: Message) -> None:
        for message in messages:
            if self.message_symbols_limit:
                text_parts = (
                    message.text[i:i + self.message_symbols_limit]
                    for i in range(
                        0,
                        len(message.text),
                        self.message_symbols_limit
                    )
                )
            else:
                text_parts = [message.text]
            for part in text_parts:
                await self.call_method(
                    "messages.send",
                    {
                        "peer_id": message.peer_id,
                        "text": part,
                        "random_id": random.randint(-1_000_000, 1_000_000)
                    }
                )

    async def send_notification(self, notification: Notification) -> None:
        for message in (
            notification.message_for_client, notification.message_for_employees
        ):
            if message is not None:
                await self.reply(message)
