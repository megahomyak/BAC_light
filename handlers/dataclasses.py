from dataclasses import dataclass

from vk.vk_related_classes import Notification


@dataclass
class HandlingResult:
    notification: Notification
    commit_needed: bool
