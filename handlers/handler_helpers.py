from typing import List

from sqlalchemy import extract

from handlers.dataclasses_ import OrdersAsStrings, NotificationWithOrders
from orm import models, db_apis
from vk.dataclasses_ import VKUserInfo, Notification
from vk.enums import NameCases
from vk.vk_worker import VKWorker


class HandlerHelpers:

    def __init__(
            self, vk_worker: VKWorker,
            users_manager: db_apis.CachedVKUsersManager,
            orders_manager: db_apis.OrdersManager) -> None:
        self.vk_worker = vk_worker
        self.users_manager = users_manager
        self.orders_manager = orders_manager

    @staticmethod
    def get_tag_from_vk_user_dataclass(user_info: VKUserInfo) -> str:
        return (
            f"[id{user_info.id}|{user_info.name} {user_info.surname}]"
        )

    async def get_orders_as_strings(
            self, orders: List[models.Order],
            include_creator_info: bool = True) -> OrdersAsStrings:
        output = []
        some_user_info_is_downloaded = False
        for order in orders:
            if include_creator_info:
                creator_info = await self.users_manager.get_user_info_by_id(
                    order.creator_vk_id, NameCases.INS  # Instrumental case
                )
                if creator_info.is_downloaded:
                    some_user_info_is_downloaded = True
                creator_tag = self.get_tag_from_vk_user_dataclass(
                    creator_info.user_info
                )
                order_contents = [
                    f"Заказ с ID {order.id}:",
                    (
                        f"Создан {creator_tag}."
                    )
                ]
            else:
                order_contents = [f"Заказ с ID {order.id}:"]
            if order.is_taken:
                taker_info = await self.users_manager.get_user_info_by_id(
                    order.creator_vk_id, NameCases.INS  # Instrumental case
                )
                if taker_info.is_downloaded:
                    some_user_info_is_downloaded = True
                taker_tag = self.get_tag_from_vk_user_dataclass(
                    taker_info.user_info
                )
                order_contents.append(
                    f"Взят {taker_tag}."
                )
            if order.is_canceled:
                canceler_info = await self.users_manager.get_user_info_by_id(
                    order.canceler_vk_id, NameCases.INS  # Instrumental case
                )
                if canceler_info.is_downloaded:
                    some_user_info_is_downloaded = True
                canceler_tag = self.get_tag_from_vk_user_dataclass(
                    canceler_info.user_info
                )
                if order.creator_vk_id == order.canceler_vk_id:
                    maybe_creator_postfix = " (создателем)"
                else:
                    maybe_creator_postfix = ""
                order_contents.append(
                    f"Отменен {canceler_tag}{maybe_creator_postfix} по причине "
                    f"\"{order.cancellation_reason}\"."
                )
            elif order.is_paid:
                order_contents.append(
                    f"Оплачен заказчиком {order.earning_date} на сумму "
                    f"{order.earnings} руб."
                )
            order_contents.append(f"Текст заказа: \"{order.text}\".")
            output.append("\n".join(order_contents))
        return OrdersAsStrings(
            output,
            some_user_info_is_downloaded
        )

    async def get_notification_with_orders(
            self, orders: List[models.Order],
            include_creator_info: bool = True) -> NotificationWithOrders:
        orders_as_strings = await self.get_orders_as_strings(
            orders, include_creator_info
        )
        return NotificationWithOrders(
            Notification(
                text_for_client="\n\n".join(
                    orders_as_strings.orders
                )
            ),
            some_user_info_is_downloaded=(
                orders_as_strings.some_user_info_is_downloaded
            )
        )

    def get_monthly_paid_orders_by_month_and_year(
            self, month: int, year: int) -> List[models.Order]:
        return self.orders_manager.get_orders(
            extract("month", models.Order.earning_date) == month,
            extract("year", models.Order.earning_date) == year,
            models.Order.is_paid
        )
