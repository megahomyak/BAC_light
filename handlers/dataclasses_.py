from dataclasses import dataclass
from typing import List

from vk.dataclasses_ import Notification


@dataclass
class OrdersAsStrings:

    orders: List[str]
    some_user_info_is_downloaded: bool


@dataclass
class NotificationWithOrders:

    notification: Notification
    some_user_info_is_downloaded: bool
