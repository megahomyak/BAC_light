import random

from simple_avk import SimpleAVK

from vk import vk_constants
from vk.message_classes import Notification, Message


class VKWorker(SimpleAVK):

    async def reply(self, *messages: Message) -> None:
        for message in messages:
            text_parts = (
                message.text[i:i + vk_constants.SYMBOLS_LIMIT]
                for i in range(
                    0,
                    len(message.text),
                    vk_constants.SYMBOLS_LIMIT
                )
            )
            for part in text_parts:
                await self.call_method(
                    "messages.send",
                    {
                        "peer_id": message.peer_id,
                        "text": part,
                        "random_id": random.randint(-1_000_000, 1_000_000),
                        "disable_mentions": 1
                    }
                )

    async def send_notifications(self, *notifications: Notification) -> None:
        for notification in notifications:
            for message in (
                notification.message_for_client,
                notification.message_for_employees
            ):
                if message is not None:
                    await self.reply(message)

    async def get_user_info(self, user_vk_id: int) -> dict:
        user_info = await self.call_method(
            "users.get",
            {
                "user_ids": user_vk_id,
                "fields": "sex"
            }
        )
        return user_info
