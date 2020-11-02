import datetime
from typing import Tuple, List, Dict, Callable

from sqlalchemy import not_

from enums import Sex, DBSessionChanged
from handlers.dataclasses import HandlingResult
from handlers.handler_helpers import HandlerHelpers, ResultSection
from lexer import lexer_classes
from orm import db_apis
from orm import models
from vk import vk_constants
from vk.vk_related_classes import Notification, UserCallbackMessages


class Handlers:

    def __init__(
            self, handler_helpers: HandlerHelpers,
            managers_container: db_apis.ManagersContainer) -> None:
        self.helpers = handler_helpers
        self.managers_container = managers_container

    async def create_order(
            self, client_vk_id: int, text: str) -> HandlingResult:
        order = models.Order(
            creator_vk_id=client_vk_id,
            text=text
        )
        self.managers_container.orders_manager.add(order)
        self.managers_container.orders_manager.flush()
        client_info = (
            await self.managers_container.users_manager.get_user_info_by_id(
                client_vk_id
            )
        )
        made_word = "сделал" if client_info.sex is Sex.MALE else "сделала"
        client_tag = self.helpers.get_tag_from_vk_user_dataclass(client_info)
        return HandlingResult(
            Notification(
                text_for_client=f"Заказ с ID {order.id} создан!",
                text_for_employees=(
                    f"Клиент {client_tag} {made_word} заказ с ID {order.id}: "
                    f"{order.text}."
                )
            ),
            DBSessionChanged.YES
        )

    async def cancel_orders(
            self, client_vk_id: int, current_chat_peer_id: int,
            order_ids: Tuple[int],
            cancellation_reason: str) -> HandlingResult:
        employees_callback: List[str] = []
        client_callback_messages = UserCallbackMessages()
        found_orders = (
            self.managers_container.orders_manager.get_orders_by_ids(order_ids)
        )
        not_owned_by_user_order_ids: List[int] = []
        paid_order_ids: List[int] = []
        already_canceled_order_ids: List[int] = []
        taken_by_other_employee_order_ids: List[int] = []
        canceled_order_ids: List[int] = []
        request_is_from_client = (
             current_chat_peer_id != vk_constants.EMPLOYEES_CHAT_PEER_ID
        )
        for order in found_orders.successful_rows:
            if request_is_from_client and order.creator_vk_id != client_vk_id:
                not_owned_by_user_order_ids.append(order.id)
            elif order.is_paid:
                paid_order_ids.append(order.id)
            elif order.is_canceled:
                already_canceled_order_ids.append(order.id)
            elif (
                order.is_taken and not order.taker_vk_id == client_vk_id
                and
                order.creator_vk_id != client_vk_id
            ):
                taken_by_other_employee_order_ids.append(order.id)
            else:
                order.canceler_vk_id = client_vk_id
                order.cancellation_reason = cancellation_reason
                canceled_order_ids.append(order.id)
                callback_str = (
                    f"{order.id} (\"{order.text}\")"
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
        user_output = self.helpers.get_order_manipulation_results_as_list(
            ResultSection(
                "ID заказов, которых просто нет", found_orders.failed_ids
            ),
            ResultSection(
                "ID оплаченных заказов, их нельзя отменить", paid_order_ids
            ),
            ResultSection(
                "ID уже отмененных заказов", already_canceled_order_ids
            ),
            ResultSection(
                (
                    "ID заказов, которые тебе не принадлежат, поэтому их "
                    "нельзя отменить"
                ),
                not_owned_by_user_order_ids
            ),
            ResultSection(
                (
                    "ID заказов, которые уже взяты другим сотрудником, "
                    "поэтому их нельзя отменить"
                ),
                taken_by_other_employee_order_ids
            ),
            ResultSection(
                "ID успешно отмененных заказов", canceled_order_ids
            )
        )
        sender_info = (
            await self.managers_container.users_manager.get_user_info_by_id(
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
        return HandlingResult(
            Notification(
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
            ),
            DBSessionChanged.MAYBE
        )

    async def get_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> HandlingResult:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(),
            no_orders_found_client_error="У тебя еще нет заказов!",
            no_orders_found_employees_error="Заказов еще нет!"
        )

    async def get_taken_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> HandlingResult:
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
            current_chat_peer_id: int) -> HandlingResult:
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
            commands: Tuple[lexer_classes.Command, ...]) -> HandlingResult:
        return HandlingResult(
            Notification(
                text_for_client=(
                    vk_constants.HELP_MESSAGE_BEGINNING + "\n\n".join(
                        [
                            command.get_full_description(include_heading=True)
                            for command in commands
                        ]
                    )
                )
            ),
            DBSessionChanged.NO
        )

    async def get_canceled_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> HandlingResult:
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
            current_chat_peer_id: int) -> HandlingResult:
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
            earnings_amount: int) -> HandlingResult:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            client_callback_messages = UserCallbackMessages()
            found_orders = (
                self.managers_container.orders_manager.get_orders_by_ids(
                    order_ids
                )
            )
            already_paid_order_ids: List[int] = []
            canceled_order_ids: List[int] = []
            not_taken_order_ids: List[int] = []
            taken_by_other_employee_order_ids: List[int] = []
            marked_as_paid_order_ids: List[int] = []
            for order in found_orders.successful_rows:
                if order.is_paid:
                    already_paid_order_ids.append(order.id)
                elif order.is_canceled:
                    canceled_order_ids.append(order.id)
                elif not order.is_taken:
                    not_taken_order_ids.append(order.id)
                elif order.taker_vk_id != employee_vk_id:
                    taken_by_other_employee_order_ids.append(order.id)
                else:
                    order.earnings = earnings_amount
                    order.earning_date = datetime.date.today()
                    marked_as_paid_order_ids.append(order.id)
                    client_callback_messages.add_message(
                        order.creator_vk_id,
                        f"{order.id} (\"{order.text}\")"
                    )
            additional_messages = ()
            if client_callback_messages.messages:
                employee_info = await (
                    self.managers_container.users_manager.get_user_info_by_id(
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
            output = self.helpers.get_order_manipulation_results_as_list(
                ResultSection(
                    "ID заказов, которых просто нет", found_orders.failed_ids
                ),
                ResultSection(
                    "ID уже оплаченных заказов", already_paid_order_ids
                ),
                ResultSection(
                    (
                        "ID заказов, которые уже кто-то отменил, поэтому их "
                        "нельзя оплатить"
                    ), canceled_order_ids
                ),
                ResultSection(
                    (
                        "ID заказов, которые еще никто не взял, поэтому их "
                        "нельзя оплатить"
                    ), not_taken_order_ids
                ),
                ResultSection(
                    (
                        "ID заказов, которые взяты не тобой, поэтому их нельзя "
                        "оплатить"
                    ), taken_by_other_employee_order_ids
                ),
                ResultSection(
                    (
                        f"ID заказов, успешно отмеченных оплаченными на сумму "
                        f"{earnings_amount} руб."
                    ), marked_as_paid_order_ids
                )
            )
            return HandlingResult(
                Notification(
                    text_for_employees=(
                        "\n".join(output)
                        if output else
                        None
                    ),
                    additional_messages=additional_messages
                ),
                DBSessionChanged.MAYBE
            )
        else:
            return HandlingResult(
                Notification(
                    text_for_client=(
                        "Отмечать заказы оплаченными могут только сотрудники!"
                    )
                ),
                DBSessionChanged.NO
            )

    async def get_monthly_paid_orders(
            self, current_chat_peer_id: int) -> HandlingResult:
        today = datetime.date.today()
        return await self.helpers.request_monthly_paid_orders(
            current_chat_peer_id, today.month, today.year
        )

    async def get_monthly_paid_orders_by_month_and_year(
            self, current_chat_peer_id: int,
            month: int, year: int) -> HandlingResult:
        return await self.helpers.request_monthly_paid_orders(
            current_chat_peer_id, month, year
        )

    async def get_monthly_paid_orders_by_month(
            self, current_chat_peer_id: int, month: int) -> HandlingResult:
        return await self.helpers.request_monthly_paid_orders(
            current_chat_peer_id, month, datetime.date.today().year
        )

    async def take_orders(
            self, current_chat_peer_id: int, user_vk_id: int,
            order_ids: Tuple[int]) -> HandlingResult:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            client_callback_messages = UserCallbackMessages()
            found_orders = (
                self.managers_container.orders_manager.get_orders_by_ids(
                    order_ids
                )
            )
            already_taken_order_ids: List[int] = []
            canceled_order_ids: List[int] = []
            taken_order_ids: List[int] = []
            for order in found_orders.successful_rows:
                if order.is_taken:
                    already_taken_order_ids.append(order.id)
                elif order.is_canceled:
                    canceled_order_ids.append(order.id)
                else:
                    order.taker_vk_id = user_vk_id
                    taken_order_ids.append(order.id)
                    client_callback_messages.add_message(
                        order.creator_vk_id,
                        f"{order.id} (\"{order.text}\")"
                    )
            additional_messages = ()
            if client_callback_messages.messages:
                employee_info = await (
                    self.managers_container.users_manager.get_user_info_by_id(
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
                    postfix=(
                        ". Подожди, пока сотрудник тебе напишет или не медли - "
                        "напиши сотруднику самостоятельно."
                    )
                )
            output = self.helpers.get_order_manipulation_results_as_list(
                ResultSection(
                    "ID заказов, которых просто нет", found_orders.failed_ids
                ),
                ResultSection(
                    "ID заказов, которые уже взяты", already_taken_order_ids
                ),
                ResultSection(
                    "ID отмененных заказов, их нельзя взять", canceled_order_ids
                ),
                ResultSection(
                    "ID успешно взятых заказов", taken_order_ids
                )
            )
            return HandlingResult(
                Notification(
                    text_for_employees=(
                        "\n".join(output)
                        if output else
                        None
                    ),
                    additional_messages=additional_messages
                ),
                DBSessionChanged.MAYBE
            )
        else:
            return HandlingResult(
                Notification(
                    text_for_client="Брать заказы могут только сотрудники!"
                ),
                DBSessionChanged.NO
            )

    async def get_active_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> HandlingResult:
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
            command_names: Tuple[str, ...]) -> HandlingResult:
        command_descriptions_as_strings = []
        quoted_not_found_commands: List[str] = []
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
                quoted_not_found_commands.append(f"\"{command_name}\"")
        return HandlingResult(
            Notification(
                text_for_client="\n\n".join(
                    (
                        (
                            f"Команда с названием "
                            f"{quoted_not_found_commands[0]} не найдена!"
                            if len(quoted_not_found_commands) == 1 else
                            f"Команды с названиями "
                            f"{', '.join(quoted_not_found_commands)} "
                            f"не найдены!"
                        ) if quoted_not_found_commands else "",
                        *command_descriptions_as_strings
                    )
                )
            ),
            DBSessionChanged.NO
        )

    async def get_order_by_id(
            self, client_vk_id: int, current_chat_peer_id: int,
            order_ids: Tuple[int, ...]) -> HandlingResult:
        found_orders = (
            self.managers_container.orders_manager.get_orders_by_ids(
                order_ids
            )
        )
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
        return HandlingResult(
            Notification(
                text_for_client="\n\n".join(output)
            ),
            DBSessionChanged.MAYBE
        )
