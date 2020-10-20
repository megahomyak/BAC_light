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


@dataclass
class RequestedVKUserInfo:

    user_info: VKUserInfo
    is_downloaded: bool
