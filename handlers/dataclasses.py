from dataclasses import dataclass

from enums import DBSessionChanged
from vk.vk_related_classes import Notification


@dataclass
class HandlingResult:

    notification: Notification
    db_changes: DBSessionChanged
