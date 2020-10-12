from orm import db_apis
from orm import orm_classes
from vk.message_classes import Message, Notification
from vk.vk_worker import VKWorker


async def create_order(
        orders_manager: db_apis.OrdersManager,
        vk_worker: VKWorker, client_vk_id: int, current_chat_peer_id: int,
        employees_chat_peer_id: int,
        text: str) -> Notification:
    order = orm_classes.Order(
        creator_vk_id=client_vk_id,
        text=text
    )
    orders_manager.add(order)
    orders_manager.commit()
    client_info = await vk_worker.get_user_info(client_vk_id)
    client_name = f"{client_info['first_name']} {client_info['last_name']}"
    print(client_info["sex"])
    made_word = "сделал" if client_info["sex"] == 2 else "сделала"
    return Notification(
        message_for_client=Message(
            f"Заказ с ID {order.id} создан!",
            current_chat_peer_id
        ),
        message_for_employees=Message(
            f"[id{client_vk_id}|Клиент {client_name}] "
            f"{made_word} заказ с ID {order.id}: {order.text}",
            employees_chat_peer_id
        )
    )
