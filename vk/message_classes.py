from dataclasses import dataclass
from typing import Optional


@dataclass
class Message:

    text: str
    peer_id: int


@dataclass
class Notification:

    message_for_employees: Optional[Message] = None
    message_for_client: Optional[Message] = None
