from dataclasses import dataclass
from typing import Optional

from vk import enums


@dataclass
class Message:

    text: str
    peer_id: int


@dataclass
class Notification:

    message_for_employees: Optional[Message] = None
    message_for_client: Optional[Message] = None


@dataclass
class NotificationTexts:

    text_for_employees: Optional[str] = None
    text_for_client: Optional[str] = None

    def to_notification(
            self,
            employees_chat_peer_id: Optional[int] = None,
            client_chat_peer_id: Optional[int] = None) -> Notification:
        return Notification(
            message_for_employees=(
                None
                if self.text_for_employees is None else
                Message(
                    self.text_for_employees,
                    employees_chat_peer_id
                )
            ),
            message_for_client=(
                None
                if self.text_for_client is None else
                Message(
                    self.text_for_client,
                    client_chat_peer_id
                )
            )
        )


@dataclass
class VKUserInfo:

    id: int
    name: str
    surname: str
    sex: enums.Sex
