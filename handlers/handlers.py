from typing import Tuple, List, Optional

from sqlalchemy.orm.exc import NoResultFound

from handlers.handler_helpers import HandlerHelpers
from orm import db_apis
from orm import orm_classes
from vk import vk_constants
from vk.message_classes import NotificationTexts
from vk.vk_worker import VKWorker


class Handlers:

    def __init__(
            self, vk_worker: VKWorker,
            orders_manager: db_apis.OrdersManager,
            handler_helpers: HandlerHelpers) -> None:
        self.vk_worker = vk_worker
        self.orders_manager = orders_manager
        self.helpers = handler_helpers

    async def create_order(
            self, client_vk_id: int, text: str) -> NotificationTexts:
        order = orm_classes.Order(
            creator_vk_id=client_vk_id,
            text=text
        )
        self.orders_manager.add(order)
        self.orders_manager.commit()
        client_info = await self.vk_worker.get_user_info(client_vk_id)
        made_word = "сделал" if client_info["sex"] == 2 else "сделала"
        return NotificationTexts(
            text_for_client=f"Заказ с ID {order.id} создан!",
            text_for_employees=(
                f"Клиент {self.helpers.get_tag_from_vk_user_info(client_info)} "
                f"{made_word} заказ с ID {order.id}: {order.text}."
            )
        )

    async def cancel_order(
            self, client_vk_id: int, current_chat_peer_id: int,
            order_ids: Tuple[int],
            cancellation_reason: Optional[str]) -> NotificationTexts:
        client_output: List[str] = []
        employees_output: List[str] = []
        for order_id in order_ids:
            try:
                order = self.orders_manager.get_order_by_id(order_id)
            except NoResultFound:
                client_output.append(f"Заказ с ID {order_id} не найден!")
            else:
                if order.is_paid:
                    client_output.append(
                        f"Заказ с ID {order_id} уже оплачен, "
                        f"его нельзя отменить!"
                    )
                elif (
                    current_chat_peer_id != vk_constants.EMPLOYEES_CHAT_PEER_ID
                    and
                    order.creator_vk_id != client_vk_id
                ):
                    client_output.append(
                        f"Заказ с ID {order_id} не твой, поэтому его "
                        f"нельзя отменить!"
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
                    client_info = await self.vk_worker.get_user_info(
                        client_vk_id
                    )
                    cancelled_word = (
                        "отменил"
                        if client_info["sex"] == 2 else
                        "отменила"
                    )
                    client_output.append(f"Заказ с ID {order.id} отменен!")
                    canceler_tag = self.helpers.get_tag_from_vk_user_info(
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
                orm_classes.Order.creator_vk_id == client_vk_id
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
                orm_classes.Order.is_taken
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
                orm_classes.Order.creator_vk_id == client_vk_id,
                orm_classes.Order.is_taken
            )
            if orders:
                return await self.helpers.get_notification_with_orders(
                    orders, include_creator_info=False
                )
            return NotificationTexts(
                text_for_client=f"Среди твоих заказов нет взятых!"
            )
