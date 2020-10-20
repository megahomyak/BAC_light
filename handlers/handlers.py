import datetime
from typing import Tuple, List, Optional

from sqlalchemy import not_
from sqlalchemy.orm.exc import NoResultFound

from handlers.handler_helpers import HandlerHelpers
from lexer import lexer_classes
from orm import db_apis
from orm import models
from orm.db_apis import CachedVKUsersManager
from vk import vk_constants
from vk.dataclasses_ import Notification, Message
from vk.enums import Sex
from vk.vk_worker import VKWorker


class Handlers:

    def __init__(
            self, vk_worker: VKWorker,
            orders_manager: db_apis.OrdersManager,
            handler_helpers: HandlerHelpers,
            users_manager: CachedVKUsersManager) -> None:
        self.vk_worker = vk_worker
        self.orders_manager = orders_manager
        self.helpers = handler_helpers
        self.users_manager = users_manager

    async def create_order(
            self, client_vk_id: int, text: str) -> Notification:
        order = models.Order(
            creator_vk_id=client_vk_id,
            text=text
        )
        self.orders_manager.add(order)
        self.orders_manager.commit()
        client_info = await self.users_manager.get_user_info_by_id(client_vk_id)
        if client_info.is_downloaded:
            self.users_manager.commit()
        # Re-writing client_info because I don't need old client_info anymore
        client_info = client_info.user_info
        made_word = "сделал" if client_info.sex is Sex.MALE else "сделала"
        return Notification(
            text_for_client=f"Заказ с ID {order.id} создан!",
            text_for_employees=(
                f"Клиент "
                f"{self.helpers.get_tag_from_vk_user_dataclass(client_info)} "
                f"{made_word} заказ с ID {order.id}: {order.text}."
            )
        )

    async def cancel_orders(
            self, client_vk_id: int, current_chat_peer_id: int,
            order_ids: Tuple[int],
            cancellation_reason: str) -> Notification:
        client_output: List[str] = []
        employees_output: List[str] = []
        at_least_one_order_is_canceled = False
        some_user_info_is_downloaded = False
        for order_id in order_ids:
            try:
                order = self.orders_manager.get_order_by_id(order_id)
            except NoResultFound:
                client_output.append(f"Заказ с ID {order_id} не найден!")
            else:
                if (
                    current_chat_peer_id != vk_constants.EMPLOYEES_CHAT_PEER_ID
                    and
                    order.creator_vk_id != client_vk_id
                ):
                    client_output.append(
                        f"Заказ с ID {order_id} не твой, поэтому его "
                        f"нельзя отменить!"
                    )
                elif order.is_paid:
                    client_output.append(
                        f"Заказ с ID {order_id} уже оплачен, "
                        f"его нельзя отменить!"
                    )
                elif order.is_canceled:
                    client_output.append(
                        f"Заказ с ID {order_id} уже отменен!"
                    )
                elif (
                    order.is_taken and not order.taker_vk_id == client_vk_id
                    and
                    order.creator_vk_id != client_vk_id
                ):
                    client_output.append(
                        f"Заказ с ID {order_id} взят другим "
                        f"сотрудником, поэтому его нельзя отменить!"
                    )
                else:
                    order.canceler_vk_id = client_vk_id
                    order.cancellation_reason = cancellation_reason
                    client_output.append(f"Заказ с ID {order.id} отменен!")
                    at_least_one_order_is_canceled = True
                    if (
                        current_chat_peer_id
                        !=
                        vk_constants.EMPLOYEES_CHAT_PEER_ID
                    ):
                        client_info = (
                            await self.users_manager.get_user_info_by_id(
                                client_vk_id
                            )
                        )
                        if client_info.is_downloaded:
                            some_user_info_is_downloaded = True
                        # Re-writing client_info because I don't need old
                        # client_info anymore
                        client_info = client_info.user_info
                        cancelled_word = (
                            "отменил"
                            if client_info.sex is Sex.MALE else
                            "отменила"
                        )
                        canceler_tag = (
                            self.helpers.get_tag_from_vk_user_dataclass(
                                client_info
                            )
                        )
                        employees_output.append(
                            f"Клиент {canceler_tag} "
                            f"{cancelled_word} заказ с ID {order.id} "
                            f"по причине \"{cancellation_reason}\"!"
                        )
        if at_least_one_order_is_canceled:
            self.orders_manager.commit()
        if some_user_info_is_downloaded:
            self.users_manager.commit()
        return Notification(
            text_for_employees=(
                "\n".join(employees_output)
                if employees_output else
                None
            ),
            text_for_client=(
                "\n".join(client_output)
                if client_output else
                None
            )
        )

    async def get_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> Notification:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(),
            no_orders_found_client_error="У тебя еще нет заказов!",
            no_orders_found_employees_error="Заказов еще нет!"
        )

    async def get_taken_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> Notification:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(
                not_(models.Order.is_canceled),
                not_(models.Order.is_paid),
                models.Order.is_taken
            ),
            no_orders_found_client_error="Среди твоих заказов нет взятых!",
            no_orders_found_employees_error="Взятых заказов еще нет!"
        )

    async def get_pending_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> Notification:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(
                not_(models.Order.is_taken),
                not_(models.Order.is_canceled)
            ),
            no_orders_found_client_error="Среди твоих заказов нет ожидающих!",
            no_orders_found_employees_error=(
                "Заказов в ожидании еще нет! "
                "(Но можно подождать новых клиентов ( ͡° ͜ʖ ͡°))"
            )                       # Should be the Lenny ^
        )

    @staticmethod
    async def get_help_message(
            commands: Tuple[lexer_classes.Command, ...]) -> Notification:
        return Notification(
            text_for_client=vk_constants.HELP_MESSAGE_BEGINNING + "\n\n".join(
                [
                    command.get_full_description(include_heading=True)
                    for command in commands
                ]
            )
        )

    async def get_canceled_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> Notification:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(
                models.Order.is_canceled
            ),
            no_orders_found_client_error="Среди твоих заказов нет отмененных!",
            no_orders_found_employees_error="Отмененных заказов еще нет!"
        )

    async def get_paid_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> Notification:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(
                models.Order.is_paid
            ),
            no_orders_found_client_error="Среди твоих заказов нет отмененных!",
            no_orders_found_employees_error=(
                "Оплаченных заказов еще нет! (Грустно!)"
            )
        )

    async def mark_orders_as_paid(
            self, employee_vk_id: int, current_chat_peer_id: int,
            order_ids: Tuple[int],
            earnings_amount: int) -> Notification:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            output: List[str] = []
            at_least_one_order_is_marked_as_paid = False
            some_user_info_is_downloaded = False
            for order_id in order_ids:
                try:
                    order = self.orders_manager.get_order_by_id(order_id)
                except NoResultFound:
                    output_str = f"Заказ с ID {order_id} не найден!"
                else:
                    if order.is_paid:
                        output_str = f"Заказ с ID {order_id} уже оплачен!"
                    elif order.is_canceled:
                        output_str = (
                            f"Заказ с ID {order_id} отменен, поэтому его "
                            f"нельзя оплатить!"
                        )
                    elif not order.is_taken:
                        output_str = (
                            f"Заказ с ID {order_id} не взят, его нельзя "
                            f"оплатить!"
                        )
                    elif order.taker_vk_id != employee_vk_id:
                        employee_info = await (
                            self.users_manager.get_user_info_by_id(
                                employee_vk_id
                            )
                        )
                        if employee_info.is_downloaded:
                            some_user_info_is_downloaded = True
                        # Re-writing employee_info because I don't need old
                        # employee_info anymore
                        employee_info = employee_info.user_info
                        taken_word = (
                            "взял"
                            if employee_info.sex is Sex.MALE else
                            "взяла"
                        )
                        output_str = (
                            f"Заказ с ID {order_id} {taken_word} не ты!"
                        )
                    else:
                        order.earnings = earnings_amount
                        order.earning_date = datetime.date.today()
                        at_least_one_order_is_marked_as_paid = True
                        output_str = (
                            f"Заказ с ID {order_id} отмечен оплаченным."
                        )
                output.append(output_str)
            if at_least_one_order_is_marked_as_paid:
                self.orders_manager.commit()
            if some_user_info_is_downloaded:
                self.users_manager.commit()
            return Notification(
                text_for_employees=(
                    "\n".join(output)
                    if output else
                    None
                )
            )
        else:
            return Notification(
                text_for_client=(
                    "Отмечать заказы оплаченными могут только сотрудники!"
                )
            )

    async def get_monthly_paid_orders(
            self, current_chat_peer_id: int) -> Notification:
        today = datetime.date.today()
        return await self.helpers.request_monthly_paid_orders(
            current_chat_peer_id, today.month, today.year
        )

    async def get_monthly_paid_orders_by_month_and_year(
            self, current_chat_peer_id: int,
            month: int, year: int) -> Notification:
        return await self.helpers.request_monthly_paid_orders(
            current_chat_peer_id, month, year
        )

    async def get_monthly_paid_orders_by_month(
            self, current_chat_peer_id: int, month: int) -> Notification:
        return await self.helpers.request_monthly_paid_orders(
            current_chat_peer_id, month, datetime.date.today().year
        )

    async def take_orders(
            self, current_chat_peer_id: int, user_vk_id: int,
            order_ids: Tuple[int]) -> Notification:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            employee_output: List[str] = []
            client_messages: List[Message] = []
            employee_tag: Optional[str] = None  # To make client message
            taken_word: Optional[str] = None  # To make client message
            at_least_one_order_is_taken = False
            some_user_info_is_downloaded = False
            for order_id in order_ids:
                try:
                    order = self.orders_manager.get_order_by_id(order_id)
                except NoResultFound:
                    employee_output.append(f"Заказ с ID {order_id} не найден!")
                else:
                    if order.is_taken:
                        employee_output.append(
                            f"Заказ с ID {order_id} уже взят!"
                        )
                    elif order.is_canceled:
                        employee_output.append(
                            f"Заказ с ID {order_id} отменен, его нельзя взять!"
                        )
                    else:
                        order.taker_vk_id = user_vk_id
                        if employee_tag is None:
                            client_info = (
                                await self.users_manager.get_user_info_by_id(
                                    user_vk_id
                                )
                            )
                            if client_info.is_downloaded:
                                some_user_info_is_downloaded = True
                            # Re-writing client_info because I don't need old
                            # client_info anymore
                            client_info = client_info.user_info
                            employee_tag = (
                                self.helpers.get_tag_from_vk_user_dataclass(
                                    client_info
                                )
                            )
                            taken_word = (
                                "взял"
                                if client_info.sex == Sex.MALE else
                                "взяла"
                            )
                            del client_info
                        employee_output.append(f"Заказ с ID {order_id} взят!")
                        client_messages.append(
                            Message(
                                (
                                    f"{employee_tag} {taken_word} твой заказ с "
                                    f"ID {order_id}! Открой ЛС или напиши ему "
                                    f"сам для обсуждения деталей заказа и "
                                    f"получения результата."
                                ),
                                order.creator_vk_id
                            )
                        )
                        at_least_one_order_is_taken = True
            if at_least_one_order_is_taken:
                self.orders_manager.commit()
            if some_user_info_is_downloaded:
                self.users_manager.commit()
            return Notification(
                text_for_employees=(
                    "\n".join(employee_output)
                    if employee_output else
                    None
                ),
                additional_messages=client_messages
            )
        else:
            return Notification(
                text_for_client="Брать заказы могут только сотрудники!"
            )

    async def get_active_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> Notification:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(
                not_(models.Order.is_paid),
                not_(models.Order.is_canceled)
            ),
            no_orders_found_client_error="Среди твоих заказов нет активных!",
            no_orders_found_employees_error="Активных заказов еще нет!"
        )

    @staticmethod
    async def get_help_message_for_specific_commands(
            commands: Tuple[lexer_classes.Command, ...],
            command_names: Tuple[str, ...]) -> Notification:
        command_descriptions: List[str] = []
        for command_name in command_names:
            for command in commands:
                if command_name in command.names:
                    command_descriptions.append(
                        command.get_full_description(include_heading=True)
                    )
        return Notification(
            text_for_client=(
                "\n\n".join(command_descriptions)
                if command_descriptions else
                "Команды с указанными названиями не найдены!"
            )
        )
