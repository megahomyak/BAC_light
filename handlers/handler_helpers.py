from typing import List

from orm import models
from vk.dataclasses_ import NotificationTexts
from vk.enums import NameCases
from vk.vk_worker import VKWorker


class HandlerHelpers:

    def __init__(self, vk_worker: VKWorker) -> None:
        self.vk_worker = vk_worker

    @staticmethod
    def get_tag_from_vk_user_info(user_info: dict) -> str:
        return (
            f"[id{user_info['id']}|"
            f"{user_info['first_name']} "
            f"{user_info['last_name']}]"
        )

    async def get_orders_as_strings(
            self, orders: List[models.Order],
            include_creator_info: bool = True) -> List[str]:
        output = []
        for order in orders:
            if include_creator_info:
                creator_info = await self.vk_worker.get_user_info(
                    order.creator_vk_id, NameCases.INS  # Instrumental case
                )
                order_contents = [
                    f"Заказ с ID {order.id}:",
                    f"Создан {self.get_tag_from_vk_user_info(creator_info)}."
                ]
            else:
                order_contents = [f"Заказ с ID {order.id}:"]
            if order.is_taken:
                taker_info = await self.vk_worker.get_user_info(
                    order.creator_vk_id, NameCases.INS  # Instrumental case
                )
                order_contents.append(
                    f"Взят {self.get_tag_from_vk_user_info(taker_info)}."
                )
            if order.is_canceled:
                canceler_info = await self.vk_worker.get_user_info(
                    order.canceler_vk_id, NameCases.INS  # Instrumental case
                )
                canceler_tag = self.get_tag_from_vk_user_info(
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
            self, orders: List[models.Order],
            include_creator_info: bool = True) -> NotificationTexts:
        return NotificationTexts(
            text_for_client="\n\n".join(
                await self.get_orders_as_strings(
                    orders, include_creator_info
                )
            )
        )
