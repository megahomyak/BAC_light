from typing import List, Tuple, Any

from sqlalchemy import extract

from enums import GrammaticalCases
from orm import models, db_apis
from vk import vk_constants
from vk.vk_related_classes import VKUserInfo, Notification
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
            include_creator_info: bool = True) -> Tuple[str, ...]:
        return tuple(
            await self.get_order_as_string(order, include_creator_info)
            for order in orders
        )

    async def get_order_as_string(
            self, order: models.Order,
            include_creator_info: bool = True) -> str:
        if include_creator_info:
            creator_info = await self.users_manager.get_user_info_by_id(
                order.creator_vk_id, GrammaticalCases.INSTRUMENTAL
            )
            creator_tag = self.get_tag_from_vk_user_dataclass(creator_info)
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
                order.creator_vk_id, GrammaticalCases.INSTRUMENTAL
            )
            taker_tag = self.get_tag_from_vk_user_dataclass(taker_info)
            order_contents.append(
                f"Взят {taker_tag}."
            )
        if order.is_canceled:
            canceler_info = await self.users_manager.get_user_info_by_id(
                order.canceler_vk_id, GrammaticalCases.INSTRUMENTAL
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
                f"\"{order.cancellation_reason}\"."
            )
        elif order.is_paid:
            order_contents.append(
                f"Оплачен заказчиком {order.earning_date} на сумму "
                f"{order.earnings} руб."
            )
        order_contents.append(f"Текст заказа: \"{order.text}\".")
        return "\n".join(order_contents)

    async def get_notification_with_orders(
            self, orders: List[models.Order],
            include_creator_info: bool = True) -> Notification:
        orders_as_strings = await self.get_orders_as_strings(
            orders, include_creator_info
        )
        return Notification(
            text_for_client="\n\n".join(
                orders_as_strings
            )
        )

    def get_monthly_paid_orders_by_month_and_year(
            self, month: int, year: int) -> List[models.Order]:
        return self.orders_manager.get_orders(
            extract("month", models.Order.earning_date) == month,
            extract("year", models.Order.earning_date) == year,
            models.Order.is_paid
        )

    async def request_orders_as_notification(
            self, client_vk_id: int, current_chat_peer_id: int,
            filters: Tuple[Any, ...], no_orders_found_client_error: str,
            no_orders_found_employees_error: str) -> Notification:
        request_is_from_employee = (
            current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID
        )
        filters = (
            filters
            if request_is_from_employee else
            (*filters, models.Order.creator_vk_id == client_vk_id)
        )  # Old filters isn't needed anymore
        orders = self.orders_manager.get_orders(*filters)
        if not orders:
            return Notification(
                # Here text_for_client will be sent to employees if orders is
                # requested in the employees' chat
                text_for_client=(
                    no_orders_found_employees_error
                    if request_is_from_employee else
                    no_orders_found_client_error
                )
            )
        notification_with_orders = (
            await self.get_notification_with_orders(
                orders,
                # If client requested the orders - creator info isn't needed,
                # because client is the creator
                include_creator_info=request_is_from_employee
            )
        )
        self.users_manager.commit_if_something_is_changed()
        return notification_with_orders

    async def request_monthly_paid_orders(
            self, current_chat_peer_id: int,
            month: int, year: int) -> Notification:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            orders = self.get_monthly_paid_orders_by_month_and_year(
                month, year
            )
            if orders:
                notification_with_orders = (
                    await self.get_notification_with_orders(
                        orders
                    )
                )
                self.users_manager.commit_if_something_is_changed()
                return notification_with_orders
            return Notification(
                text_for_employees=(
                    f"За {month} месяц {year} года не оплачено еще ни одного "
                    f"заказа!"
                )
            )
        else:
            return Notification(
                text_for_client=(
                    "Получать месячные оплаченные заказы могут только "
                    "сотрудники!"
                )
            )
