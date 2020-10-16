import random

from simple_avk import SimpleAVK

from vk import vk_constants
from vk.dataclasses_ import Notification, Message
from vk.enums import NameCases, Sex


class VKWorker(SimpleAVK):

    async def reply(self, *messages: Message) -> None:
        for message in messages:
            text_parts = (
                message.text[i:i + vk_constants.SYMBOLS_PER_MESSAGE]
                for i in range(
                    0,
                    len(message.text),
                    vk_constants.SYMBOLS_PER_MESSAGE
                )
            )
            for part in text_parts:
                await self.call_method(
                    "messages.send",
                    {
                        "peer_id": message.peer_id,
                        "message": part,
                        "random_id": random.randint(-1_000_000, 1_000_000),
                        "disable_mentions": 1
                    }
                )

    async def send_notifications(self, *notifications: Notification) -> None:
        for notification in notifications:
            if notification.message_for_client is not None:
                await self.reply(notification.message_for_client)
            if (
                notification.message_for_employees is not None
                and
                (
                    notification.message_for_client is None
                    or
                    notification.message_for_client.peer_id
                    !=
                    notification.message_for_employees.peer_id
                )
            ):
                await self.reply(notification.message_for_employees)

    async def get_user_info(
            self, user_vk_id: int,
            name_case: NameCases = NameCases.NOM) -> dict:
        user_info = await self.call_method(
            "users.get",
            {
                "user_ids": user_vk_id,
                "fields": "sex",
                "name_case": name_case.value
            }
        )
        user_info = user_info[0]
        user_info["sex"] = Sex.MALE if user_info["sex"] == 2 else Sex.FEMALE
        return user_info
