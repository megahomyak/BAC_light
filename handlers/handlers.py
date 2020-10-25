import datetime
from typing import Tuple, List, Dict, Callable

from sqlalchemy import not_

from enums import Sex
from handlers.handler_helpers import HandlerHelpers
from lexer import lexer_classes
from orm import db_apis
from orm import models
from orm.db_apis import CachedVKUsersManager
from vk import vk_constants
from vk.vk_related_classes import Notification, UserCallbackMessages
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
        self.users_manager.commit_if_something_is_changed()
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
        employees_callback: List[str] = []
        client_callback_messages = UserCallbackMessages()
        found_orders = self.orders_manager.get_orders_by_ids(order_ids)
        user_output: List[str] = [
            f"Заказ с ID {failed_id} не найден!"
            for failed_id in found_orders.failed_ids
        ]
        request_is_from_client = (
             current_chat_peer_id != vk_constants.EMPLOYEES_CHAT_PEER_ID
        )
        for order in found_orders.successful_rows:
            if request_is_from_client and order.creator_vk_id != client_vk_id:
                user_output_str = (
                    f"Заказ с ID {order.id} не твой, поэтому его "
                    f"нельзя отменить!"
                )
            elif order.is_paid:
                user_output_str = (
                    f"Заказ с ID {order.id} уже оплачен, "
                    f"его нельзя отменить!"
                )
            elif order.is_canceled:
                user_output_str = f"Заказ с ID {order.id} уже отменен!"
            elif (
                order.is_taken and not order.taker_vk_id == client_vk_id
                and
                order.creator_vk_id != client_vk_id
            ):
                user_output_str = (
                    f"Заказ с ID {order.id} взят другим "
                    f"сотрудником, поэтому его нельзя отменить!"
                )
            else:
                order.canceler_vk_id = client_vk_id
                order.cancellation_reason = cancellation_reason
                user_output_str = f"Заказ с ID {order.id} отменен!"
                callback_str = (
                    f"заказ с ID {order.id} (и текстом \"{order.text}\")"
                )
                if request_is_from_client:
                    employees_callback.append(
                        callback_str
                    )
                else:
                    client_callback_messages.add_message(
                        order.creator_vk_id,
                        callback_str
                    )
            user_output.append(user_output_str)
        self.orders_manager.commit_if_something_is_changed()
        self.users_manager.commit_if_something_is_changed()
        sender_info = (
            await self.users_manager.get_user_info_by_id(
                client_vk_id
            )
        )
        canceled_word = (
            "отменил"
            if sender_info.sex is Sex.MALE else
            "отменила"
        )
        canceler_tag = (
            self.helpers.get_tag_from_vk_user_dataclass(
                sender_info
            )
        )
        additional_messages = (
            client_callback_messages.to_messages(
                prefix=(
                    f"{canceler_tag} {canceled_word} твои заказы по причине "
                    f"\"{cancellation_reason}\": "
                ),
                separator=", ",
                postfix="."
            )
            if client_callback_messages.messages else
            ()
        )
        return Notification(
            text_for_employees=(
                (
                    f"Клиент {canceler_tag} {canceled_word} заказы: "
                    + "\n".join(employees_callback)
                )
                if employees_callback else
                None
            ),
            text_for_client=(
                "\n".join(user_output)
                if user_output else
                None
            ),
            additional_messages=additional_messages
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
                models.Order.is_canceled,
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
                models.Order.is_paid,
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
            client_callback_messages = UserCallbackMessages()
            found_orders = self.orders_manager.get_orders_by_ids(order_ids)
            output: List[str] = [
                f"Заказ с ID {failed_id} не найден!"
                for failed_id in found_orders.failed_ids
            ]
            for order in found_orders.successful_rows:
                if order.is_paid:
                    output_str = f"Заказ с ID {order.id} уже оплачен!"
                elif order.is_canceled:
                    output_str = (
                        f"Заказ с ID {order.id} отменен, поэтому его "
                        f"нельзя оплатить!"
                    )
                elif not order.is_taken:
                    output_str = (
                        f"Заказ с ID {order.id} не взят, его нельзя "
                        f"оплатить!"
                    )
                elif order.taker_vk_id != employee_vk_id:
                    employee_info = await (
                        self.users_manager.get_user_info_by_id(
                            employee_vk_id
                        )
                    )
                    marked_word = (
                        "взял"
                        if employee_info.sex is Sex.MALE else
                        "взяла"
                    )
                    output_str = (
                        f"Заказ с ID {order.id} {marked_word} не ты!"
                    )
                else:
                    order.earnings = earnings_amount
                    order.earning_date = datetime.date.today()
                    output_str = (
                        f"Заказ с ID {order.id} отмечен оплаченным."
                    )
                    client_callback_messages.add_message(
                        order.creator_vk_id,
                        f"заказ с ID {order.id} (и текстом \"{order.text}\")"
                    )
                output.append(output_str)
            self.orders_manager.commit_if_something_is_changed()
            self.users_manager.commit_if_something_is_changed()
            additional_messages = ()
            if client_callback_messages.messages:
                employee_info = (
                    await self.users_manager.get_user_info_by_id(
                        employee_vk_id
                    )
                )
                employee_tag = (
                    self.helpers.get_tag_from_vk_user_dataclass(
                        employee_info
                    )
                )
                marked_word = (
                    "отметил"
                    if employee_info.sex == Sex.MALE else
                    "отметила"
                )
                additional_messages = client_callback_messages.to_messages(
                    prefix=(
                        f"{employee_tag} {marked_word} оплаченными твои заказы "
                        f"на сумму {earnings_amount} руб.: "
                    ),
                    separator=", ",
                    postfix="."
                )
            return Notification(
                text_for_employees=(
                    "\n".join(output)
                    if output else
                    None
                ),
                additional_messages=additional_messages
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
            client_callback_messages = UserCallbackMessages()
            found_orders = self.orders_manager.get_orders_by_ids(order_ids)
            output: List[str] = [
                f"Заказ с ID {failed_id} не найден!"
                for failed_id in found_orders.failed_ids
            ]
            for order in found_orders.successful_rows:
                if order.is_taken:
                    output_str = f"Заказ с ID {order.id} уже взят!"
                elif order.is_canceled:
                    output_str = (
                        f"Заказ с ID {order.id} отменен, его нельзя взять!"
                    )
                else:
                    order.taker_vk_id = user_vk_id
                    output_str = f"Заказ с ID {order.id} взят!"
                    client_callback_messages.add_message(
                        order.creator_vk_id,
                        f"заказ с ID {order.id} (и текстом \"{order.text}\")"
                    )
                output.append(output_str)
            self.orders_manager.commit_if_something_is_changed()
            self.users_manager.commit_if_something_is_changed()
            additional_messages = ()
            if client_callback_messages.messages:
                employee_info = (
                    await self.users_manager.get_user_info_by_id(
                        user_vk_id
                    )
                )
                employee_tag = (
                    self.helpers.get_tag_from_vk_user_dataclass(
                        employee_info
                    )
                )
                taken_word = (
                    "взял"
                    if employee_info.sex == Sex.MALE else
                    "взяла"
                )
                additional_messages = client_callback_messages.to_messages(
                    prefix=(
                        f"{employee_tag} {taken_word} твои заказы: "
                    ),
                    separator=", ",
                    postfix=". Открой ЛС или напиши сотруднику самостоятельно."
                )
            return Notification(
                text_for_employees=(
                    "\n".join(output)
                    if output else
                    None
                ),
                additional_messages=additional_messages
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
            command_descriptions: Dict[str, List[Callable]],
            command_names: Tuple[str, ...]) -> Notification:
        command_descriptions_as_strings = []
        for command_name in command_names:
            try:
                command_descriptions_as_strings.extend(
                    (
                        # Here desc_func is a Command.get_full_description,
                        # if I set Command.get_full_description as a type -
                        # I wouldn't get any IDE hints anyway
                        desc_func(include_heading=True)
                        for desc_func in command_descriptions[command_name]
                    )
                )
            except KeyError:
                pass
        return Notification(
            text_for_client=(
                "\n\n".join(command_descriptions_as_strings)
                if command_descriptions_as_strings else
                "Команды с указанными названиями не найдены!"
            )
        )

    async def get_order_by_id(
            self, client_vk_id: int,
            current_chat_peer_id: int,
            order_ids: Tuple[int, ...]) -> Notification:
        found_orders = self.orders_manager.get_orders_by_ids(order_ids)
        output: List[str] = [
            f"Заказ с ID {failed_id} не найден!"
            for failed_id in found_orders.failed_ids
        ]
        request_is_from_client = (
            current_chat_peer_id != vk_constants.EMPLOYEES_CHAT_PEER_ID
        )
        for order in found_orders.successful_rows:
            if (
                request_is_from_client
                and
                order.creator_vk_id != client_vk_id
            ):
                output.append(f"Заказ с ID {order.id} тебе не принадлежит!")
            else:
                output.append(
                    await self.helpers.get_order_as_string(
                        order,
                        # If request is from the client - no need to include
                        # creator info, because client is the creator
                        include_creator_info=not request_is_from_client
                    )
                )
        return Notification(
            text_for_client="\n\n".join(output)
        )
