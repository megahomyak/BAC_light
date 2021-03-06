import datetime
from typing import Tuple, List, Dict, Callable

import simple_avk
from sqlalchemy import not_

import orm.exceptions
from enums import GrammaticalCases
from handlers.dataclasses import HandlingResult
from handlers.handler_helpers import HandlerHelpers, ResultSection
from orm import db_apis
from orm import models
from vk.enums import Sex
from vk.vk_config import VkConfig
from vk.vk_related_classes import Notification, UserCallbackMessages, Message
from vk.vk_worker import VKWorker


# noinspection PyMethodMayBeStatic
class Handlers:

    def __init__(
            self, handler_helpers: HandlerHelpers,
            managers_container: db_apis.ManagersContainer, vk_worker: VKWorker,
            vk_config: VkConfig):
        self.helpers = handler_helpers
        self.managers_container = managers_container
        self.vk_worker = vk_worker
        self.vk_config = vk_config

    async def create_order(
            self, current_chat_peer_id: int,
            client_vk_id: int, text: str) -> HandlingResult:
        order = models.Order(creator_vk_id=client_vk_id, text=text)
        self.managers_container.orders_manager.add(order)
        self.managers_container.orders_manager.flush()
        if current_chat_peer_id != self.vk_config.EMPLOYEES_CHAT_PEER_ID:
            client_info = (await (
                self.managers_container.users_manager
                .get_user_info_by_vk_id(client_vk_id)
            ))  # This looks ugly and not pythonic :(
            made_word = "сделал" if client_info.sex is Sex.MALE else "сделала"
            client_tag = self.helpers.get_tag_from_vk_user_dataclass(
                client_info
            )
            return HandlingResult(
                Notification(
                    text_for_client=f"Заказ с ID {order.id} создан!",
                    text_for_employees=(
                        f"Клиент {client_tag} {made_word} заказ с ID "
                        f"{order.id}: \"{order.text}\"."
                    )
                ), commit_needed=True
            )
        return HandlingResult(
            Notification(text_for_employees=f"Заказ с ID {order.id} создан!"),
            commit_needed=True
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
        not_owned_by_user_order_ids = []
        paid_order_ids = []
        already_canceled_order_ids = []
        taken_by_other_employee_order_ids = []
        canceled_order_ids = []
        request_is_from_client = (
            current_chat_peer_id != self.vk_config.EMPLOYEES_CHAT_PEER_ID
        )
        for order in found_orders.successful_rows:
            if request_is_from_client and order.creator_vk_id != client_vk_id:
                not_owned_by_user_order_ids.append(order.id)
            elif order.is_paid:
                paid_order_ids.append(order.id)
            elif order.is_canceled:
                already_canceled_order_ids.append(order.id)
            elif (
                order.is_taken and order.taker_vk_id != client_vk_id
                and order.creator_vk_id != client_vk_id
            ):
                taken_by_other_employee_order_ids.append(order.id)
            else:
                order.canceler_vk_id = client_vk_id
                order.cancellation_reason = cancellation_reason
                canceled_order_ids.append(order.id)
                callback_str = f"ID {order.id} (\"{order.text}\")"
                if request_is_from_client:
                    employees_callback.append(callback_str)
                else:
                    client_callback_messages.add_message(
                        order.creator_vk_id, callback_str
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
                ), not_owned_by_user_order_ids
            ),
            ResultSection(
                (
                    "ID заказов, которые уже взяты другим сотрудником, "
                    "поэтому их нельзя отменить"
                ), taken_by_other_employee_order_ids
            ),
            ResultSection(
                "ID успешно отмененных заказов", canceled_order_ids
            )
        )
        sender_info = (
            await self.managers_container.users_manager.get_user_info_by_vk_id(
                client_vk_id
            )
        )
        canceled_word = "отменил" if sender_info.sex is Sex.MALE else "отменила"
        canceler_tag = self.helpers.get_tag_from_vk_user_dataclass(sender_info)
        additional_messages = (
            client_callback_messages.to_messages(
                prefix=(
                    f"{canceler_tag} {canceled_word} твои заказы по причине "
                    f"\"{cancellation_reason}\": "
                ),
                separator=", ",
                postfix="."
            ) if client_callback_messages.messages else ()
        )
        return HandlingResult(
            Notification(
                text_for_employees=(
                    (
                        f"Клиент {canceler_tag} {canceled_word} заказы "
                        f"по причине \"{cancellation_reason}\": "
                        + "\n".join(employees_callback)
                    ) if employees_callback else None
                ),
                text_for_client="\n".join(user_output) if user_output else None,
                additional_messages=additional_messages
            ), commit_needed=True
        )

    async def get_orders(
            self, client_vk_id: int, current_chat_peer_id: int,
            limit: int) -> HandlingResult:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(),
            no_orders_found_client_error="У тебя еще нет заказов!",
            no_orders_found_employees_error="Заказов еще нет!",
            limit=limit
        )

    async def get_taken_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> HandlingResult:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(
                not_(models.Order.is_canceled), not_(models.Order.is_paid),
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
                not_(models.Order.is_taken), not_(models.Order.is_canceled)
            ),
            no_orders_found_client_error="Среди твоих заказов нет ожидающих!",
            no_orders_found_employees_error=(
                "Заказов в ожидании еще нет! "
                "(Но можно подождать новых клиентов ( ͡° ͜ʖ ͡°))"
            )                       # Should be the Lenny ^
        )

    async def get_help_message(
            self, current_chat_peer_id: int,
            full_commands_help_message: str,
            commands_only_for_clients_message: str) -> HandlingResult:
        return HandlingResult(
            Notification(text_for_client=(
                full_commands_help_message
                if current_chat_peer_id == self.vk_config.EMPLOYEES_CHAT_PEER_ID
                else commands_only_for_clients_message
            )), commit_needed=False
        )

    async def get_canceled_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int,
            limit: int) -> HandlingResult:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(models.Order.is_canceled,),
            no_orders_found_client_error="Среди твоих заказов нет отмененных!",
            no_orders_found_employees_error="Отмененных заказов еще нет!",
            limit=limit
        )

    async def get_paid_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int,
            limit: int) -> HandlingResult:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(models.Order.is_paid,),
            no_orders_found_client_error="Среди твоих заказов нет отмененных!",
            no_orders_found_employees_error=(
                "Оплаченных заказов еще нет! (Грустно!)"
            ),
            limit=limit
        )

    async def mark_orders_as_paid(
            self, employee_vk_id: int, order_ids: Tuple[int],
            earnings_amount: int) -> HandlingResult:
        client_callback_messages = UserCallbackMessages()
        found_orders = (
            self.managers_container.orders_manager.get_orders_by_ids(order_ids)
        )
        already_paid_order_ids = []
        canceled_order_ids = []
        not_taken_order_ids = []
        taken_by_other_employee_order_ids = []
        marked_as_paid_order_ids = []
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
                    f"ID {order.id} (\"{order.text}\")"
                )
        additional_messages = ()
        if client_callback_messages.messages:
            employee_info = await (
                self.managers_container.users_manager.get_user_info_by_vk_id(
                    employee_vk_id
                )
            )
            employee_tag = (
                self.helpers.get_tag_from_vk_user_dataclass(employee_info)
            )
            marked_word = (
                "отметил" if employee_info.sex == Sex.MALE else "отметила"
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
                text_for_employees="\n".join(output) if output else None,
                additional_messages=additional_messages
            ), commit_needed=True
        )

    async def get_monthly_paid_orders(
            self, year: int, month: int) -> HandlingResult:
        orders = self.helpers.get_monthly_paid_orders_by_month_and_year(
            month, year
        )
        if orders:
            notification_with_orders = (
                await self.helpers.get_notification_with_orders(orders)
            )
            return HandlingResult(notification_with_orders, commit_needed=True)
        return HandlingResult(
            Notification(
                text_for_employees=(
                    f"За {month} месяц {year} года не оплачено еще ни "
                    f"одного заказа!"
                )
            ), commit_needed=False
        )

    async def take_orders(
            self, user_vk_id: int, order_ids: Tuple[int]) -> HandlingResult:
        # Allowed only for employees
        client_callback_messages = UserCallbackMessages()
        found_orders = (
            self.managers_container.orders_manager.get_orders_by_ids(order_ids)
        )
        already_taken_order_ids = []
        canceled_order_ids = []
        taken_order_ids = []
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
                    f"ID {order.id} (\"{order.text}\")"
                )
        additional_messages = ()
        if client_callback_messages.messages:
            employee_info = await (
                self.managers_container.users_manager.get_user_info_by_vk_id(
                    user_vk_id
                )
            )
            employee_tag = (
                self.helpers.get_tag_from_vk_user_dataclass(employee_info)
            )
            taken_word = "взял" if employee_info.sex == Sex.MALE else "взяла"
            additional_messages = client_callback_messages.to_messages(
                prefix=(
                    f"{employee_tag} {taken_word} твои заказы: "
                ),
                separator=", ",
                postfix=(
                    ". Открой ЛС, чтобы сотрудник мог отправить тебе "
                    "результаты или обсудить некоторые детали."
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
                text_for_employees="\n".join(output) if output else None,
                additional_messages=additional_messages
            ), commit_needed=True
        )

    async def get_active_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> HandlingResult:
        return await self.helpers.request_orders_as_notification(
            client_vk_id, current_chat_peer_id,
            filters=(
                not_(models.Order.is_paid), not_(models.Order.is_canceled)
            ),
            no_orders_found_client_error="Среди твоих заказов нет активных!",
            no_orders_found_employees_error="Активных заказов еще нет!"
        )

    async def get_help_message_for_specific_commands(
            self, command_descriptions: Dict[str, List[Callable[..., str]]],
            command_names: Tuple[str, ...]) -> HandlingResult:
        command_descriptions_as_strings = []
        quoted_not_found_commands: List[str] = []
        for command_name in command_names:
            try:
                command_descriptions_as_strings.extend(
                    # Here desc_func is a Command.get_full_description,
                    # if I set Command.get_full_description as a type -
                    # I wouldn't get any IDE hints anyway
                    desc_func()
                    for desc_func in command_descriptions[command_name]
                )
            except KeyError:
                quoted_not_found_commands.append(f"\"{command_name}\"")
        successful_output = "\n".join(command_descriptions_as_strings)
        return HandlingResult(
            Notification(
                text_for_client="\n\n".join(
                    (
                        f"Команда с названием "
                        f"{quoted_not_found_commands[0]} не найдена!"
                        if len(quoted_not_found_commands) == 1 else
                        f"Команды с названиями "
                        f"{', '.join(quoted_not_found_commands)} "
                        f"не найдены!",
                        successful_output
                    )
                ) if quoted_not_found_commands else successful_output
            ), commit_needed=False
        )

    async def get_order_by_id(
            self, client_vk_id: int, current_chat_peer_id: int,
            order_ids: Tuple[int, ...]) -> HandlingResult:
        found_orders = (
            self.managers_container.orders_manager.get_orders_by_ids(order_ids)
        )
        output: List[str] = [
            f"Заказ с ID {failed_id} не найден!"
            for failed_id in found_orders.failed_ids
        ]
        request_is_from_client = (
            current_chat_peer_id != self.vk_config.EMPLOYEES_CHAT_PEER_ID
        )
        for order in found_orders.successful_rows:
            if request_is_from_client and order.creator_vk_id != client_vk_id:
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
            ), commit_needed=True
        )

    async def get_monthly_earnings(
            self, year: int, month: int) -> HandlingResult:
        # Allowed only for employees
        orders = self.helpers.get_monthly_paid_orders_by_month_and_year(
            month, year
        )
        if orders:
            earnings: Dict[int, int] = {}
            total_earnings = 0
            for order in orders:
                total_earnings += order.earnings
                try:
                    earnings[order.taker_vk_id] += order.earnings
                except KeyError:
                    earnings[order.taker_vk_id] = order.earnings
            earnings_as_strings: List[str] = []
            for employee_vk_id, taker_earnings in earnings.items():
                employee_info = await (
                    self.managers_container.users_manager
                    .get_user_info_by_vk_id(employee_vk_id)
                )
                earned_word = (
                    "заработал"
                    if employee_info.sex is Sex.MALE else
                    "заработала"
                )
                employee_tag = self.helpers.get_tag_from_vk_user_dataclass(
                    employee_info
                )
                earnings_as_strings.append(
                    f"{employee_tag} {earned_word} {taker_earnings} руб."
                )
            return HandlingResult(
                Notification(
                    text_for_employees="\n".join(
                        (
                            f"Общий доход: {total_earnings} руб.",
                            *earnings_as_strings
                        )
                    )
                ), commit_needed=True
            )
        return HandlingResult(
            Notification(
                text_for_employees=(
                    f"За {month} месяц {year} года не заработано ни рубля!"
                )
            ), commit_needed=False
        )

    async def create_order_offline(
            self, employee_vk_id: int, client_vk_id_or_tag: str,
            text: str) -> HandlingResult:
        try:
            client_info = await (
                self.managers_container.users_manager.get_user_info_by_vk_id(
                    client_vk_id_or_tag, GrammaticalCases.GENITIVE
                )
            )
        except simple_avk.MethodError:
            return HandlingResult(
                Notification(
                    text_for_employees=(
                        f"Пользователя с VK ID {client_vk_id_or_tag} нет!"
                    )
                ), commit_needed=False
            )
        else:
            client_vk_id = client_info.id
            order = models.Order(
                creator_vk_id=client_vk_id,
                real_creator_vk_id=employee_vk_id,
                text=text
            )
            self.managers_container.orders_manager.add(order)
            self.managers_container.orders_manager.flush()
            full_client_tag = self.helpers.get_tag_from_vk_user_dataclass(
                client_info
            )
            employee_tag = self.helpers.get_tag_from_vk_user_dataclass(
                await (
                    self.managers_container.users_manager
                    .get_user_info_by_vk_id(
                        employee_vk_id, GrammaticalCases.INSTRUMENTAL
                    )
                )
            )
            return HandlingResult(
                Notification(
                    text_for_employees=(
                        f"Заказ с ID {order.id} создан от лица "
                        f"{full_client_tag}!"
                    ),
                    additional_messages=[
                        Message(
                            (
                                f"От твоего лица {employee_tag} создан заказ с "
                                f"ID {order.id} и текстом \"{text}\"! Если вы "
                                f"не просили этого делать - напишите "
                                f"администрации."
                            ),
                            client_vk_id
                        )
                    ]
                ), commit_needed=True
            )

    async def clear_cache(self, user_vk_id: int) -> HandlingResult:
        user_tag = self.helpers.get_tag_from_vk_user_dataclass(
            await self.vk_worker.get_user_info(user_vk_id)
        )
        try:
            self.managers_container.users_manager.delete_user_info(
                models.CachedVKUser.vk_id == user_vk_id
            )
        except orm.exceptions.NoRowsFound:
            return HandlingResult(
                Notification(
                    text_for_client=(
                        f"{user_tag}, информация о тебе не сохранена! (Сейчас "
                        f"твои имя и фамилия были скачаны временно, не "
                        f"сохранены)"
                    )
                ), commit_needed=False
            )
        return HandlingResult(
            Notification(
                text_for_client=(
                    f"{user_tag}, твои имена очищены! (Сейчас "
                    f"твои имя и фамилия были скачаны временно, не "
                    f"сохранены)"
                )
            ), commit_needed=True
        )

    async def get_memo(self) -> HandlingResult:
        return HandlingResult(
            Notification(
                text_for_client=(
                    f"Памятка по использованию бота:\n\n"
                    f"{self.vk_config.MEMO_FOR_USERS}"
                )
            ), commit_needed=False
        )
