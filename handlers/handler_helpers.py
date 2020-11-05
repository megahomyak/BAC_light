from dataclasses import dataclass
from typing import List, Optional

from sqlalchemy import extract

from enums import GrammaticalCases
from handlers.dataclasses import HandlingResult
from orm import models, db_apis
from orm.enums import DBSessionChanged
from vk import vk_constants
from vk.vk_related_classes import VKUserInfo, Notification


@dataclass
class ResultSection:

    beginning: str
    row_ids: List[int]


class HandlerHelpers:

    def __init__(self, managers_container: db_apis.ManagersContainer) -> None:
        self.managers_container = managers_container

    @staticmethod
    def get_tag_from_vk_user_dataclass(user_info: VKUserInfo) -> str:
        return (
            f"[id{user_info.id}|{user_info.name} {user_info.surname}]"
        )

    async def get_orders_as_strings(
            self, orders: List[models.Order],
            include_creator_info: bool = True) -> List[str]:
        return [
            await self.get_order_as_string(order, include_creator_info)
            for order in orders
        ]

    async def get_order_as_string(
            self, order: models.Order,
            include_creator_info: bool = True) -> str:
        if include_creator_info:
            creator_info = await (
                self.managers_container.users_manager.get_user_info_by_id(
                    order.creator_vk_id, GrammaticalCases.INSTRUMENTAL
                )
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
            taker_info = await (
                self.managers_container.users_manager.get_user_info_by_id(
                    order.taker_vk_id, GrammaticalCases.INSTRUMENTAL
                )
            )
            taker_tag = self.get_tag_from_vk_user_dataclass(taker_info)
            order_contents.append(
                f"Взят {taker_tag}."
            )
        if order.is_canceled:
            canceler_info = await (
                self.managers_container.users_manager.get_user_info_by_id(
                    order.canceler_vk_id, GrammaticalCases.INSTRUMENTAL
                )
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
            include_creator_info: bool = True,
            limit_for_header: Optional[int] = None) -> Notification:
        orders_as_strings = await self.get_orders_as_strings(
            orders, include_creator_info
        )
        if limit_for_header is not None:
            orders_as_strings.insert(0, f"Лимит - {limit_for_header} заказов.")
        return Notification(
            text_for_client="\n\n".join(
                orders_as_strings
            )
        )

    def get_monthly_paid_orders_by_month_and_year(
            self, month: int, year: int) -> List[models.Order]:
        return self.managers_container.orders_manager.get_orders(
            extract("month", models.Order.earning_date) == month,
            extract("year", models.Order.earning_date) == year,
            models.Order.is_paid
        )

    async def request_orders_as_notification(
            self, client_vk_id: int, current_chat_peer_id: int,
            filters: tuple, no_orders_found_client_error: str,
            no_orders_found_employees_error: str,
            limit: Optional[int] = None) -> HandlingResult:
        request_is_from_employee = (
            current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID
        )
        filters = (
            filters
            if request_is_from_employee else
            (*filters, models.Order.creator_vk_id == client_vk_id)
        )  # Old filters isn't needed anymore
        orders = self.managers_container.orders_manager.get_orders(
            *filters,
            limit=limit
        )
        if not orders:
            return HandlingResult(
                Notification(
                    # Here text_for_client will be sent to employees if orders
                    # is requested in the employees' chat
                    text_for_client=(
                        no_orders_found_employees_error
                        if request_is_from_employee else
                        no_orders_found_client_error
                    )
                ),
                DBSessionChanged.NO
            )
        notification_with_orders = (
            await self.get_notification_with_orders(
                orders,
                # If client requested the orders - creator info isn't needed,
                # because client is the creator
                include_creator_info=request_is_from_employee,
                limit_for_header=limit
            )
        )
        self.managers_container.users_manager.commit_if_something_is_changed()
        return HandlingResult(notification_with_orders, DBSessionChanged.MAYBE)

    @staticmethod
    def get_order_manipulation_results_as_list(
            *sections: ResultSection) -> List[str]:
        return [
            f"{section.beginning}: {', '.join(map(str, section.row_ids))}"
            for section in sections
            if section.row_ids
        ]
