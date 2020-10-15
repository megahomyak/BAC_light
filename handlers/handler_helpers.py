from typing import List

from orm import orm_classes
from vk.message_classes import NotificationTexts
from vk.vk_worker import VKWorker


def get_tag_from_vk_user_info(user_info: dict) -> str:
    return (
        f"[id{user_info['id']}|"
        f"{user_info['first_name']} "
        f"{user_info['last_name']}]"
    )


async def get_orders_as_strings(
        orders: List[orm_classes.Order], vk_worker: VKWorker,
        include_creator_info: bool = True) -> List[str]:
    output = []
    for order in orders:
        if include_creator_info:
            creator_info = await vk_worker.get_user_info(
                order.creator_vk_id, "ins"  # Instrumental case
            )
            order_contents = [
                f"Заказ с ID {order.id}:",
                f"Создан {get_tag_from_vk_user_info(creator_info)}."
            ]
        else:
            order_contents = [f"Заказ с ID {order.id}:"]
        if order.is_taken:
            taker_info = await vk_worker.get_user_info(
                order.creator_vk_id, "ins"  # Instrumental case
            )
            order_contents.append(
                f"Взят {get_tag_from_vk_user_info(taker_info)}."
            )
        if order.is_canceled:
            canceler_info = await vk_worker.get_user_info(
                order.canceler_vk_id, "ins"  # Instrumental case
            )
            canceler_tag = get_tag_from_vk_user_info(
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
        orders: List[orm_classes.Order], vk_worker: VKWorker,
        include_creator_info: bool = True) -> NotificationTexts:
    return NotificationTexts(
        text_for_client="\n\n".join(
            await get_orders_as_strings(
                orders, vk_worker, include_creator_info
            )
        )
    )
