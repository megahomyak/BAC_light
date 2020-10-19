from typing import List

from sqlalchemy import extract

from orm import models, db_apis
from vk.dataclasses_ import VKUserInfo, Notification
from vk.enums import NameCases
from vk.vk_worker import VKWorker


class HandlerHelpers:

    def __init__(
            self, vk_worker: VKWorker,
            users_manager: db_apis.VKUsersManager,
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
            include_creator_info: bool = True) -> List[str]:
        output = []
        for order in orders:
            if include_creator_info:
                creator_info = await self.users_manager.get_user_info_by_id(
                    order.creator_vk_id, NameCases.INS  # Instrumental case
                )
                order_contents = [
                    f"Заказ с ID {order.id}:",
                    (
                        f"Создан "
                        f"{self.get_tag_from_vk_user_dataclass(creator_info)}."
                    )
                ]
            else:
                order_contents = [f"Заказ с ID {order.id}:"]
            if order.is_taken:
                taker_info = await self.users_manager.get_user_info_by_id(
                    order.creator_vk_id, NameCases.INS  # Instrumental case
                )
                order_contents.append(
                    f"Взят {self.get_tag_from_vk_user_dataclass(taker_info)}."
                )
            if order.is_canceled:
                canceler_info = await self.users_manager.get_user_info_by_id(
                    order.canceler_vk_id, NameCases.INS  # Instrumental case
                )
                canceler_tag = self.get_tag_from_vk_user_dataclass(
                    canceler_info
                )
                if order.creator_vk_id == order.canceler_vk_id:
                    maybe_creator_postfix = " (создателем)"
                else:
                    maybe_creator_postfix = ""
                order_contents.append(
                    f"Отменен {canceler_tag}{maybe_creator_postfix} по причине "
                    f"{order.cancellation_reason}."
                )
            elif order.is_paid:
                order_contents.append(
                    f"Оплачен заказчиком {order.earning_date}."
                )
            order_contents.append(f"Текст заказа: {order.text}.")
            output.append("\n".join(order_contents))
        return output

    async def get_notification_with_orders(
            self, orders: List[models.Order],
            include_creator_info: bool = True) -> Notification:
        return Notification(
            text_for_client="\n\n".join(
                await self.get_orders_as_strings(
                    orders, include_creator_info
                )
            )
        )

    def get_monthly_paid_orders_by_month_and_year(
            self, month: int, year: int) -> List[models.Order]:
        return self.orders_manager.get_orders(
            extract("month", models.Order.earning_date) == month,
            extract("year", models.Order.earning_date) == year,
            models.Order.is_paid
        )
