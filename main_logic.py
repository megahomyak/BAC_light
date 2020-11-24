import asyncio
import datetime
import inspect
import traceback
from typing import (
    NoReturn, Optional, List, Tuple, Dict, Callable, Union,
    Coroutine
)

import aiohttp
import simple_avk
import simplest_logger

import lexer.exceptions
import lexer.generators
from enums import GrammaticalCases
from handlers.handler_helpers import HandlerHelpers
from handlers.handlers import Handlers, HandlingResult
from lexer.enums import IntTypes
from lexer.lexer_classes import Command, Arg, Context, ConstantContext
from lexer.lexer_implementations import (
    StringArgType, VKSenderIDMetadataElement, VKPeerIDMetadataElement,
    SequenceArgType, IntArgType, CommandsConstantMetadataElement,
    CommandDescriptionsConstantMetadataElement, CurrentYearMetadataElement,
    CurrentMonthMetadataElement, MonthNumberArgType
)
from orm import db_apis
from vk import vk_config
from vk.enums import Sex
from vk.vk_related_classes import Message
from vk.vk_worker import VKWorker


class MainLogic:

    def __init__(
            self, managers_container: db_apis.ManagersContainer,
            vk_worker: VKWorker, handlers: Handlers,
            logger: Optional[simplest_logger.Logger] = None,
            log_command_parsing_errors: bool = True,
            commit_changes: bool = True):
        self.managers_container = managers_container
        self.vk_worker = vk_worker
        self.logger = logger
        self.log_command_parsing_errors = log_command_parsing_errors
        self.get_tag_from_vk_user_dataclass = (
            handlers.helpers.get_tag_from_vk_user_dataclass
        )
        self.commit_changes = commit_changes
        self.commands: Tuple[Command, ...] = (
            *lexer.generators.get_getter_commands_for_common_orders(
                ru_names=("заказы",),
                eng_names=("orders",),
                orders_name="заказы",
                handler=handlers.get_orders
            ),
            *lexer.generators.get_getter_commands_for_common_orders(
                ru_names=("отмененные",),
                eng_names=("canceled",),
                orders_name="отмененные заказы",
                handler=handlers.get_canceled_orders
            ),
            *lexer.generators.get_getter_commands_for_common_orders(
                ru_names=("оплаченные",),
                eng_names=("paid",),
                orders_name="оплаченные заказы",
                handler=handlers.get_paid_orders
            ),
            Command(
                names=("заказ", "order", "заказать"),
                handler=handlers.create_order,
                description=(
                    "создает новый заказ (заказ содержит только текст, "
                    "картинки туда не попадают!)"
                ),
                metadata=(VKPeerIDMetadataElement, VKSenderIDMetadataElement),
                arguments=(Arg("текст заказа", StringArgType()),)
            ),
            Command(
                names=("отменить", "отмена", "cancel"),
                handler=handlers.cancel_orders,
                description=(
                    "отменяет заказ (клиентам нельзя отменять чужие заказы; "
                    "сотрудникам нельзя отменять заказы, взятые другим "
                    "сотрудником; всем нельзя отменять оплаченные заказы)"
                ),
                metadata=(VKSenderIDMetadataElement, VKPeerIDMetadataElement),
                arguments=(
                    Arg(
                        "ID заказов, которые нужно отменить (через запятую)",
                        SequenceArgType(IntArgType())
                    ),
                    Arg("причина отмены", StringArgType())
                )
            ),
            Command(
                names=("взятые", "взятые заказы", "taken", "taken orders"),
                handler=handlers.get_taken_orders,
                description=(
                    "показывает все взятые заказы, которые не отменены и не "
                    "оплачены (если спрашивает клиент - только заказы этого же "
                    "клиента)"
                ),
                metadata=(VKSenderIDMetadataElement, VKPeerIDMetadataElement)
            ),
            Command(
                names=("в ожидании", "waiting", "pending", "ожидающие"),
                handler=handlers.get_pending_orders,
                description=(
                    "показывает все заказы, которые еще не взяты и не отменены "
                    "(если спрашивает клиент - только заказы этого же "
                    "клиента)"
                ),
                metadata=(VKSenderIDMetadataElement, VKPeerIDMetadataElement)
            ),
            Command(
                names=("команды", "помощь", "help", "commands"),
                handler=handlers.get_help_message,
                description="показывает помощь по командам и их написанию",
                constant_metadata=(CommandsConstantMetadataElement,)
            ),
            Command(
                names=("оплачено", "оплатить", "pay", "mark as paid"),
                handler=handlers.mark_orders_as_paid,
                description=(
                    "отмечает заказ оплаченным (это могут делать только "
                    "сотрудники, причем могут помечать оплаченными лишь те "
                    "заказы, которые взяли сами)"
                ),
                metadata=(VKSenderIDMetadataElement,),
                arguments=(
                    Arg(
                        (
                            "ID заказов, которые нужно отметить оплаченными "
                            "(через запятую)"
                        ), SequenceArgType(IntArgType())
                    ),
                    Arg(
                        "выручка (с каждого указанного заказа)",
                        IntArgType(IntTypes.UNSIGNED)
                    )
                ),
                allowed_only_for_employees=True
            ),
            Command(
                names=("месячное", "monthly"),
                handler=handlers.get_monthly_paid_orders,
                description="показывает оплаченные заказы за месяц",
                metadata=(
                    CurrentYearMetadataElement,
                    CurrentMonthMetadataElement
                ),
                allowed_only_for_employees=True
            ),
            Command(
                names=("месячное", "monthly"),
                handler=handlers.get_monthly_paid_orders,
                description=(
                    "показывает оплаченные заказы за указанный месяц "
                    "указанного года"
                ),
                arguments=(
                    Arg("номер года", IntArgType()),
                    Arg("номер месяца", MonthNumberArgType())
                ),
                allowed_only_for_employees=True
            ),
            Command(
                names=("месячное", "monthly"),
                handler=handlers.get_monthly_paid_orders,
                description=(
                    "показывает оплаченные заказы за указанный месяц (только "
                    "для сотрудников)"
                ),
                metadata=(CurrentYearMetadataElement,),
                arguments=(Arg("номер месяца", MonthNumberArgType()),),
                allowed_only_for_employees=True
            ),
            Command(
                names=("взять", "take"),
                handler=handlers.take_orders,
                description=(
                    "отмечает заказы как взятые и отсылает уведомления о "
                    "взятии клиентам"
                ),
                metadata=(VKSenderIDMetadataElement,),
                arguments=(
                    Arg(
                        (
                            "ID заказов, которые нужно отметить "
                            "взятыми (через запятую)"
                        ), SequenceArgType(IntArgType())
                    ),
                ),
                allowed_only_for_employees=True
            ),
            Command(
                names=("активные", "active"),
                handler=handlers.get_active_orders,
                description=(
                    "показывает все заказы, которые не отменены и не оплачены "
                    "(если спрашивает клиент - только заказы этого же клиента)"
                ),
                metadata=(VKSenderIDMetadataElement, VKPeerIDMetadataElement)
            ),
            Command(
                names=("команды", "помощь", "help", "commands"),
                handler=handlers.get_help_message_for_specific_commands,
                description=(
                    "показывает помощь по конкретным командам и их написанию"
                ),
                constant_metadata=(CommandDescriptionsConstantMetadataElement,),
                arguments=(
                    Arg(
                        (
                            "команды, к которым нужно получить подсказку "
                            "(через запятую)"
                        ), SequenceArgType(StringArgType())
                    ),
                )
            ),
            Command(
                names=("инфо", "info", "information", "информация"),
                handler=handlers.get_order_by_id,
                description=(
                    "показывает заказы с указанными ID (для клиентов - лишь "
                    "если заказ принадлежит им)"
                ),
                metadata=(VKSenderIDMetadataElement, VKPeerIDMetadataElement),
                arguments=(
                    Arg(
                        "ID заказов (через запятую)",
                        SequenceArgType(IntArgType())
                    ),
                )
            ),
            Command(
                names=("доход", "earnings", "income", "revenue"),
                handler=handlers.get_monthly_earnings,
                description="показывает доход за месяц",
                metadata=(
                    CurrentYearMetadataElement, CurrentMonthMetadataElement
                ),
                allowed_only_for_employees=True
            ),
            Command(
                names=("доход", "earnings", "income", "revenue"),
                handler=handlers.get_monthly_earnings,
                description=(
                    "показывает доход за указанный месяц указанного года"
                ),
                arguments=(
                    Arg("номер года", IntArgType()),
                    Arg("номер месяца", MonthNumberArgType())
                ),
                allowed_only_for_employees=True
            ),
            Command(
                names=("доход", "earnings", "income", "revenue"),
                handler=handlers.get_monthly_earnings,
                description="показывает доход за указанный месяц",
                metadata=(CurrentYearMetadataElement,),
                arguments=(Arg("номер месяца", MonthNumberArgType()),),
                allowed_only_for_employees=True
            ),
            Command(
                names=("оффлайн", "offline"),
                handler=handlers.create_order_offline,
                description=(
                    "создает новый заказ от лица указанного клиента "
                    "(на тот случай, если клиент хочет сделать заказ оффлайн; "
                    "кроме указания VK ID клиента, от лица которого будет "
                    "сделан заказ, эта команда работает так же, как и просто "
                    "/заказ)"
                ),
                metadata=(VKSenderIDMetadataElement,),
                arguments=(
                    Arg(
                        "тэг или ID клиента в ВК", StringArgType(),
                        (
                            "тэг или ID клиента, за которого будет сделан "
                            "заказ"
                        )
                    ),
                    Arg("текст заказа", StringArgType())
                ),
                allowed_only_for_employees=True
            ),
            Command(
                names=(
                    "очистить кеш", "очистить кэш", "удалить кеш",
                    "удалить кэш", "clear cache", "delete cache", "remove cache"
                ),
                handler=handlers.clear_cache,
                description=(
                    "удаляет всю информацию, которую бот сохранил о твоей "
                    "странице ВК (заказы остаются). Может быть полезно при "
                    "смене имени, фамилии или пола в ВК, чтобы бот обновил "
                    "свою базу данных"
                ),
                metadata=(VKSenderIDMetadataElement,)
            ),
            Command(
                names=("памятка", "memo"),
                handler=handlers.get_memo,
                description="показывает памятку по использованию бота"
            )
        )
        command_descriptions: Dict[str, List[Callable]] = {}
        for command in self.commands:
            for name in command.names:
                try:
                    command_descriptions[name].append(
                        command.get_full_description
                    )
                except KeyError:
                    command_descriptions[name] = [command.get_full_description]
        self.constant_context = ConstantContext(
            self.commands, command_descriptions
        )

    async def handle_command(
            self, current_chat_peer_id: int, command: str,
            vk_message_info: dict) -> List[Message]:
        error_args_amount = 0
        for command_ in self.commands:
            try:
                converted_command = command_.convert_command_to_args(command)
            except lexer.exceptions.ParsingError as parsing_error:
                if parsing_error.args_num > error_args_amount:
                    error_args_amount = parsing_error.args_num
            else:
                if (
                    command_.allowed_only_for_employees
                    and current_chat_peer_id != vk_config.EMPLOYEES_CHAT_PEER_ID
                ):
                    return [Message(
                        (
                            f"Команда \"{converted_command.name}\" "
                            f"доступна только сотрудникам (ее нужно "
                            f"написать в чате для сотрудников)!"
                        ), current_chat_peer_id
                    )]
                handling_result: Union[HandlingResult, Coroutine] = (
                    command_.handler(
                        *command_.get_converted_metadata(
                            Context(vk_message_info, datetime.date.today())
                        ),
                        *command_.get_converted_constant_metadata(
                            self.constant_context
                        ),
                        *command_.fillers,
                        *converted_command.arguments
                    )
                )
                if inspect.isawaitable(handling_result):
                    handling_result: HandlingResult = await handling_result
                if self.commit_changes and handling_result.commit_needed:
                    self.managers_container.commit()
                return handling_result.notification.to_messages(
                    client_peer_id=current_chat_peer_id
                )
        if error_args_amount == 0:
            error_msg = "Ошибка обработки команды на её названии!"
        else:
            error_msg = (
                f"Ошибка обработки команды на аргументе номер "
                f"{error_args_amount} (он неправильный или пропущен)"
            )
        if self.logger is not None and self.log_command_parsing_errors:
            from_id = vk_message_info['from_id']
            chat_name = (
                "чате для сотрудников"
                if current_chat_peer_id == vk_config.EMPLOYEES_CHAT_PEER_ID else
                "ЛС"
            )
            if error_args_amount == 0:
                self.logger.info(
                    f"Ошибка обработки команды \"{command}\" от пользователя с "
                    f"VK ID {from_id} в {chat_name} на её названии!"
                )
            else:
                self.logger.info(
                    f"Ошибка обработки команды \"{command}\" от пользователя с "
                    f"VK ID {from_id} в {chat_name} на аргументе номер "
                    f"{error_args_amount} (он неправильный или пропущен)"
                )
        return [Message(error_msg, current_chat_peer_id)]

    async def reply_to_vk_message(
            self, current_chat_peer_id: int, command: str,
            message_info: dict) -> None:
        done_replies = await self.vk_worker.multiple_reply(
            await self.handle_command(
                current_chat_peer_id, command, message_info
            )
        )
        ids_of_people_who_blacklisted_the_bot = []
        for reply in done_replies:
            exception = reply.exception
            if (
                isinstance(exception, simple_avk.MethodError)
                # Can't send messages to user without permission
                and exception.error_code == 901
            ):
                ids_of_people_who_blacklisted_the_bot.append(
                    reply.message.peer_id
                )
            else:
                if exception is not None:
                    raise exception
        if ids_of_people_who_blacklisted_the_bot:
            users = [
                await (
                    self.managers_container
                    .users_manager
                    .get_user_info_by_vk_id(id_, GrammaticalCases.GENITIVE)
                )
                for id_ in ids_of_people_who_blacklisted_the_bot
            ]
            tags = [
                self.get_tag_from_vk_user_dataclass(user) for user in users
            ]
            tags_str = " и ".join(
                [i for i in (", ".join(tags[:-1]), tags[-1]) if i]
            )
            if len(users) == 1:
                if users[0].sex == Sex.MALE:
                    them_he_or_she_word = "него"
                    they_he_or_she_word = "он"
                    wrote_word = "писал"
                else:
                    them_he_or_she_word = "неё"
                    they_he_or_she_word = "она"
                    wrote_word = "писала"
            else:
                them_he_or_she_word = "них"
                they_he_or_she_word = "они"
                wrote_word = "писали"
            await self.vk_worker.reply(
                Message((
                    f"Невозможно отправить сообщения для {tags_str}, "
                    f"потому что {they_he_or_she_word} никогда боту не "
                    f"{wrote_word} или бот у {them_he_or_she_word} в ЧС."
                ), current_chat_peer_id)
            )

    async def future_done_callback(
            self, peer_id: int, text: str,
            future: asyncio.Future) -> None:
        exc = future.exception()
        if exc:
            if self.logger is not None:
                chat_name = (
                    "чате для сотрудников"
                ) if peer_id == vk_config.EMPLOYEES_CHAT_PEER_ID else "ЛС"
                self.logger.error(
                    f"Ошибка на команде \"{text}\" в {chat_name}:\n" + "".join(
                        traceback.TracebackException.from_exception(
                            exc
                        ).format()
                    )
                )
            await self.vk_worker.reply(Message(
                f"Тут у юзера при обработке команды \"{text}\" произошла "
                f"ошибка \"{str(exc)}\", это в логах тоже есть, "
                f"гляньте, разберитесь...", vk_config.EMPLOYEES_CHAT_PEER_ID
            ))
            if peer_id != vk_config.EMPLOYEES_CHAT_PEER_ID:
                await self.vk_worker.reply(Message(
                    f"При обработке команды \"{text}\" произошла ошибка. "
                    f"Она была залоггирована, админы - уведомлены.", peer_id
                ))

    async def listen_for_vk_events(self) -> NoReturn:
        async for message_info in self.vk_worker.listen_for_messages():
            text: str = message_info["text"]
            peer_id: int = message_info["peer_id"]
            if text.startswith("/"):
                text = text[1:]  # Cutting /
                asyncio.create_task(
                    self.reply_to_vk_message(peer_id, text, message_info)
                ).add_done_callback(lambda future: asyncio.create_task(
                    self.future_done_callback(peer_id, text, future)
                ))


async def main():
    async with aiohttp.ClientSession() as aiohttp_session:
        vk_worker = VKWorker(
            simple_avk.SimpleAVK(
                aiohttp_session,
                vk_config.TOKEN,
                vk_config.GROUP_ID
            )
        )
        db_session = db_apis.get_db_session("sqlite:///BAC_light.db")
        managers_container = db_apis.ManagersContainer(
            db_apis.OrdersManager(db_session),
            db_apis.CachedVKUsersManager(
                db_session,
                vk_worker,
                simplest_logger.Logger("users_caching.log")
            )
        )
        main_logic = MainLogic(
            managers_container,
            vk_worker,
            Handlers(
                HandlerHelpers(managers_container),
                managers_container,
                vk_worker
            ),
            simplest_logger.Logger("command_errors.log"),
            log_command_parsing_errors=False
        )
        await main_logic.listen_for_vk_events()


if __name__ == "__main__":
    asyncio.run(main())
