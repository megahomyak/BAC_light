from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple, Iterable

from vk import enums, vk_constants


@dataclass
class Message:

    text: str
    peer_id: int


@dataclass
class Notification:

    text_for_employees: Optional[str] = None
    text_for_client: Optional[str] = None
    additional_messages: Optional[Iterable[Message]] = None

    def to_messages(self, client_peer_id: int) -> List[Message]:
        messages = []
        if self.text_for_client is not None:
            messages.append(
                Message(
                    self.text_for_client,
                    client_peer_id
                )
            )
        if (
            self.text_for_employees is not None
            and
            (
                client_peer_id != vk_constants.EMPLOYEES_CHAT_PEER_ID
                or
                self.text_for_client is None
            )
        ):
            messages.append(
                Message(
                    self.text_for_employees,
                    vk_constants.EMPLOYEES_CHAT_PEER_ID
                )
            )
        if self.additional_messages is not None:
            messages.extend(self.additional_messages)
        return messages


@dataclass
class VKUserInfo:

    id: int
    name: str
    surname: str
    sex: enums.Sex


class UserCallbackMessages:

    """
    This class is needed to register callback messages, which will be sent to
    clients, for example, when employee takes multiple orders.
    """

    def __init__(self):
        # Dict[user_vk_id, List[message_text]]
        self.messages: Dict[int, List[str]] = {}

    def add_message(self, user_vk_id: int, message_text: str) -> None:
        try:
            self.messages[user_vk_id].append(message_text)
        except KeyError:
            self.messages[user_vk_id] = [message_text]

    def to_messages(self, separator="\n\n") -> Tuple[Message, ...]:
        return tuple(
            Message(separator.join(texts), client_vk_id_)
            for client_vk_id_, texts in self.messages.items()
        )
