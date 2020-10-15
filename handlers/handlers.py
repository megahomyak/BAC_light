from typing import Tuple, List, Optional

from sqlalchemy.orm.exc import NoResultFound

from handlers import handler_helpers as helpers
from orm import db_apis
from orm import orm_classes
from vk import vk_constants
from vk.message_classes import NotificationTexts
from vk.vk_worker import VKWorker


async def create_order(
        orders_manager: db_apis.OrdersManager,
        vk_worker: VKWorker,
        client_vk_id: int,
        text: str) -> NotificationTexts:
    order = orm_classes.Order(
        creator_vk_id=client_vk_id,
        text=text
    )
    orders_manager.add(order)
    orders_manager.commit()
    client_info = await vk_worker.get_user_info(client_vk_id)
    made_word = "сделал" if client_info["sex"] == 2 else "сделала"
    return NotificationTexts(
        text_for_client=f"Заказ с ID {order.id} создан!",
        text_for_employees=(
            f"Клиент {helpers.get_tag_from_vk_user_info(client_info)} "
            f"{made_word} заказ с ID {order.id}: {order.text}"
        )
    )


async def cancel_order(
        orders_manager: db_apis.OrdersManager,
        vk_worker: VKWorker,
        client_vk_id: int, current_chat_peer_id: int,
        order_ids: Tuple[int],
        cancellation_reason: Optional[str]) -> NotificationTexts:
    client_output: List[str] = []
    employees_output: List[str] = []
    for order_id in order_ids:
        try:
            order = orders_manager.get_order_by_id(order_id)
        except NoResultFound:
            client_output.append(f"Заказ с ID {order_id} не найден!")
        else:
            if order.is_paid:
                client_output.append(
                    f"Заказ с ID {order_id} уже оплачен, его нельзя отменить!"
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
                orders_manager.commit()
                client_info = await vk_worker.get_user_info(client_vk_id)
                cancelled_word = (
                    "отменил"
                    if client_info["sex"] == 2 else
                    "отменила"
                )
                client_output.append(f"Заказ с ID {order.id} отменен!")
                employees_output.append(
                    f"Клиент {helpers.get_tag_from_vk_user_info(client_info)} "
                    f"{cancelled_word} заказ с ID {order.id} "
                    f"по причине \"{cancellation_reason}\""
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
        orders_manager: db_apis.OrdersManager,
        vk_worker: VKWorker,
        client_vk_id: int,
        current_chat_peer_id: int) -> NotificationTexts:
    if current_chat_peer_id == vk_constants.EMPLOYEES_CHAT_PEER_ID:
        orders = orders_manager.get_orders()
        if orders:
            output = []
            for order in orders:
                creator_info = await vk_worker.get_user_info(
                    order.creator_vk_id, "ins"  # Instrumental case
                )
                order_contents = [
                    f"Заказ с ID {order.id}:",
                    f"Создан {helpers.get_tag_from_vk_user_info(creator_info)}."
                ]
                if order.is_taken:
                    taker_info = await vk_worker.get_user_info(
                        order.creator_vk_id, "ins"  # Instrumental case
                    )
                    order_contents.append(
                        f"Взят {helpers.get_tag_from_vk_user_info(taker_info)}."
                    )
                if order.is_canceled:
                    canceler_info = await vk_worker.get_user_info(
                        order.canceler_vk_id, "ins"  # Instrumental case
                    )
                    canceler_tag = helpers.get_tag_from_vk_user_info(
                        canceler_info
                    )
                    order_contents.append(
                        f"Отменен {canceler_tag} по причине "
                        f"{order.cancellation_reason}."
                    )
                elif order.is_paid:
                    order_contents.append(
                        f"Оплачен заказчиком {order.earning_date}."
                    )
                order_contents.append(f"Текст заказа: {order.text}.")
                output.append("\n".join(order_contents))
            return NotificationTexts(
                text_for_client="\n\n".join(output)
            )
        return NotificationTexts(
            text_for_client="Заказов еще нет!"
        )
    else:
        orders = orders_manager.get_orders(
            orm_classes.Order.creator_vk_id == client_vk_id
        )
        if orders:
            output = []
            for order in orders:
                order_contents = [f"Заказ с ID {order.id}:"]
                if order.is_taken:
                    taker_info = await vk_worker.get_user_info(
                        order.creator_vk_id, "ins"  # Instrumental case
                    )
                    order_contents.append(
                        f"Взят {helpers.get_tag_from_vk_user_info(taker_info)}."
                    )
                if order.is_canceled:
                    canceler_info = await vk_worker.get_user_info(
                        order.canceler_vk_id, "ins"  # Instrumental case
                    )
                    canceler_tag = helpers.get_tag_from_vk_user_info(
                        canceler_info
                    )
                    order_contents.append(
                        f"Отменен {canceler_tag} по причине "
                        f"{order.cancellation_reason}."
                    )
                elif order.is_paid:
                    order_contents.append(
                        f"Оплачен заказчиком {order.earning_date}."
                    )
                order_contents.append(f"Текст заказа: {order.text}.")
                output.append("\n".join(order_contents))
            return NotificationTexts(
                text_for_client="\n\n".join(output)
            )
        client_info = await vk_worker.get_user_info(client_vk_id)
        order_word = (
            'заказал'
            if client_info['sex'] == 2 else
            'заказала'
        )
        return NotificationTexts(
            text_for_client=f"Ты еще ничего не {order_word}!"
        )
