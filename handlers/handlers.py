import datetime
from typing import Tuple, List

from sqlalchemy import not_, extract
from sqlalchemy.orm.exc import NoResultFound

from handlers.handler_helpers import HandlerHelpers
from lexer import lexer_classes
from orm import db_apis
from orm import models
from orm.db_apis import VKUsersManager
from vk import vk_constants
from vk.dataclasses_ import NotificationTexts
from vk.enums import Sex
from vk.vk_worker import VKWorker


class Handlers:

    def __init__(
            self, vk_worker: VKWorker,
            orders_manager: db_apis.OrdersManager,
            handler_helpers: HandlerHelpers,
            users_manager: VKUsersManager) -> None:
        self.vk_worker = vk_worker
        self.orders_manager = orders_manager
        self.helpers = handler_helpers
        self.users_manager = users_manager

    async def create_order(
            self, client_vk_id: int, text: str) -> NotificationTexts:
        order = models.Order(
            creator_vk_id=client_vk_id,
            text=text
        )
        self.orders_manager.add(order)
        self.orders_manager.commit()
        client_info = await self.users_manager.get_user_info_by_id(client_vk_id)
        made_word = "сделал" if client_info.sex is Sex.MALE else "сделала"
        return NotificationTexts(
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
            cancellation_reason: str) -> NotificationTexts:
        client_output: List[str] = []
        employees_output: List[str] = []
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
                    self.orders_manager.commit()
                    client_info = await self.users_manager.get_user_info_by_id(
                        client_vk_id
                    )
                    cancelled_word = (
                        "отменил"
                        if client_info.sex is Sex.MALE else
                        "отменила"
                    )
                    client_output.append(f"Заказ с ID {order.id} отменен!")
                    canceler_tag = self.helpers.get_tag_from_vk_user_dataclass(
                        client_info
                    )
                    employees_output.append(
                        f"Клиент {canceler_tag} "
                        f"{cancelled_word} заказ с ID {order.id} "
                        f"по причине \"{cancellation_reason}\"!"
                    )
        return NotificationTexts(
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
            current_chat_peer_id: int) -> NotificationTexts:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            orders = self.orders_manager.get_orders()
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders
                )
            return NotificationTexts(
                text_for_client="Заказов еще нет!"
            )
        else:
            orders = self.orders_manager.get_orders(
                models.Order.creator_vk_id == client_vk_id
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders, include_creator_info=False
                )
            client_info = await self.vk_worker.get_user_info(client_vk_id)
            order_word = (
                'заказал'
                if client_info['sex'] == 2 else
                'заказала'
            )
            return NotificationTexts(
                text_for_client=f"Ты еще ничего не {order_word}!"
            )

    async def get_taken_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> NotificationTexts:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            orders = self.orders_manager.get_orders(
                not_(models.Order.is_canceled),
                not_(models.Order.is_paid),
                models.Order.is_taken
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders
                )
            return NotificationTexts(
                text_for_client="Взятых заказов еще нет!"
            )
        else:
            orders = self.orders_manager.get_orders(
                models.Order.creator_vk_id == client_vk_id,
                not_(models.Order.is_canceled),
                not_(models.Order.is_paid),
                models.Order.is_taken
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders, include_creator_info=False
                )
            return NotificationTexts(
                text_for_client=f"Среди твоих заказов нет взятых!"
            )

    async def get_pending_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> NotificationTexts:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            orders = self.orders_manager.get_orders(
                not_(models.Order.is_taken),
                not_(models.Order.is_canceled)
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders
                )
            return NotificationTexts(
                text_for_client=(
                    "Заказов в ожидании еще нет! "
                    "(Но можно подождать новых клиентов ( ͡° ͜ʖ ͡°))"
                )                       # Should be the Lenny ^
            )
        else:
            orders = self.orders_manager.get_orders(
                models.Order.creator_vk_id == client_vk_id,
                not_(models.Order.is_taken),
                not_(models.Order.is_canceled)
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders, include_creator_info=False
                )
            return NotificationTexts(
                text_for_client=f"Среди твоих заказов нет ожидающих!"
            )

    @staticmethod
    async def get_help_message(
            commands: Tuple[lexer_classes.Command]) -> NotificationTexts:
        return NotificationTexts(
            text_for_client="\n\n".join(
                [
                    command.get_full_description(include_heading=True)
                    for command in commands
                ]
            ) + vk_constants.HELP_MESSAGE_ENDING
        )

    async def get_canceled_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> NotificationTexts:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            orders = self.orders_manager.get_orders(
                models.Order.is_canceled
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders
                )
            return NotificationTexts(
                text_for_client="Отмененных заказов еще нет!"
            )
        else:
            orders = self.orders_manager.get_orders(
                models.Order.creator_vk_id == client_vk_id,
                models.Order.is_canceled
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders, include_creator_info=False
                )
            return NotificationTexts(
                text_for_client=f"Среди твоих заказов нет отмененных!"
            )

    async def get_paid_orders(
            self, client_vk_id: int,
            current_chat_peer_id: int) -> NotificationTexts:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            orders = self.orders_manager.get_orders(
                models.Order.is_paid
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders
                )
            return NotificationTexts(
                text_for_client="Оплаченных заказов еще нет! (Грустно!)"
            )
        else:
            orders = self.orders_manager.get_orders(
                models.Order.creator_vk_id == client_vk_id,
                models.Order.is_paid
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders, include_creator_info=False
                )
            return NotificationTexts(
                text_for_client=(
                    f"Среди твоих заказов нет оплаченных! (А лучше бы были!)"
                )
            )

    async def make_orders_paid(
            self, employee_vk_id: int, current_chat_peer_id: int,
            order_ids: Tuple[int],
            earnings_amount: int) -> NotificationTexts:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            output: List[str] = []
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
                        output_str = (
                            f"Заказ с ID {order_id} отмечен оплаченным."
                        )
                output.append(output_str)
            return NotificationTexts(
                text_for_client=(
                    "\n".join(output)
                    if output else
                    None
                )
            )
        else:
            return NotificationTexts(
                text_for_client=(
                    "Отмечать заказы оплаченными могут только сотрудники!"
                )
            )

    async def get_monthly_paid_orders(
            self, current_chat_peer_id: int) -> NotificationTexts:
        if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
            today = datetime.date.today()
            orders = self.orders_manager.get_orders(
                extract("month", models.Order.earning_date) == today.month,
                extract("year", models.Order.earning_date) == today.year,
                models.Order.is_paid
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders
                )
            return NotificationTexts(
                text_for_client=(
                    "За этот месяц не оплачено еще ни одного заказа!"
                )
            )
        else:
            return NotificationTexts(
                text_for_client=(
                    "Получать месячные оплаченные заказы могут только "
                    "сотрудники!"
                )
            )
