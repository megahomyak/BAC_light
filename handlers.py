from orm import db_apis
from orm import orm_classes
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
    client_name = f"{client_info['first_name']} {client_info['last_name']}"
    made_word = "сделал" if client_info["sex"] == 2 else "сделала"
    return NotificationTexts(
        text_for_client=f"Заказ с ID {order.id} создан!",
        text_for_employees=(
            f"[id{client_vk_id}|Клиент {client_name}] "
            f"{made_word} заказ с ID {order.id}: {order.text}"
        )
    )
