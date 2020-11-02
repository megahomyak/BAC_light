from dataclasses import dataclass
from typing import Any, List, Iterable

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, Query
from sqlalchemy.orm.exc import NoResultFound

import exceptions
from enums import GrammaticalCases
from orm import models
from vk import vk_related_classes
from vk.vk_worker import VKWorker


class MySession(Session):

    """
    Added only a commit_if_something_is_changed method to the sqlalchemy's
    Session class, the rest remains the same.
    """

    def commit_if_something_is_changed(self) -> None:
        """
        Makes a commit if there are staging (non-flushed) changes.

        Warnings:
            If autoflush is enabled - it wouldn't work!
        """
        # If autoflush is enabled - this lists will be empty, so that can lead
        # to the situation, where commit isn't working
        if self.new or self.dirty or self.deleted:
            self.commit()


def get_db_session(path_to_sqlite_db: str) -> MySession:
    sql_engine = create_engine(path_to_sqlite_db)
    models.DeclarativeBase.metadata.create_all(sql_engine)
    return MySession(sql_engine, autoflush=False)
    # autoflush is disabled because I check for non-flushed objects when
    # checking for staging changes before commit


@dataclass
class FoundResults:

    failed_ids: List[int]
    successful_rows: List[models.Order]


class OrdersManager:

    def __init__(self, sqlalchemy_session: MySession) -> None:
        self.db_session = sqlalchemy_session

    def _get_query(self) -> Query:
        return (
            self.db_session
            .query(models.Order)
            .order_by(models.Order.id.desc())
        )

    def get_orders(self, *filters: Any) -> List[models.Order]:
        return (
            self._get_query()
            .filter(*filters)
            .all()
        ) if filters else (
            self._get_query()
            .all()
        )

    def get_orders_by_ids(self, order_ids: Iterable[int]) -> FoundResults:
        orders: List[models.Order] = (
            self._get_query()
            .filter(models.Order.id.in_(order_ids))
            .all()
        )
        failed_ids: List[int] = list(order_ids)
        for order in orders:
            failed_ids.remove(order.id)
        return FoundResults(failed_ids, orders)

    def commit(self) -> None:
        self.db_session.commit()

    def commit_if_something_is_changed(self) -> None:
        self.db_session.commit_if_something_is_changed()

    def delete(self, *orders: models.Order) -> None:
        for order in orders:
            self.db_session.delete(order)

    def add(self, *orders: models.Order) -> None:
        self.db_session.add_all(orders)

    def flush(self) -> None:
        self.db_session.flush()


class CachedVKUsersManager:

    def __init__(
            self, sqlalchemy_session: MySession,
            vk_worker: VKWorker) -> None:
        self.db_session = sqlalchemy_session
        self.vk_worker = vk_worker

    async def get_user_info_by_id(
            self, vk_id: int,
            name_case: GrammaticalCases = GrammaticalCases.NOMINATIVE
            ) -> vk_related_classes.VKUserInfo:
        # noinspection GrazieInspection
        # because ] in the penultimate explanation string is opened, but
        # LanguageTool doesn't see the opening square bracket.
        r"""
        Gets user info by ID. If no user info found - downloads it, even with
        the name cases.

        Warnings:
            Not even async-safe! Like, really! Here's an example:

            [ task1: method is called                               | task2: - ]

            [ task1: no user info found, let's wait and download it | task2: - ]

            [ task1: *waits*   | task2: method is called                       ]

            [ task1: *waits*   | task2: no user info found, let's wait and
            download it! Hey, but we already made this in task1! ]

            IDK how to fix it actually.

        Args:
            vk_id: VK ID of user, info of who will be found.
            name_case: case of user's name and surname.

        Returns:
            info about the specified user
        """
        try:
            user_info: models.CachedVKUser = (
                self.db_session
                .query(models.CachedVKUser)
                .filter(models.CachedVKUser.vk_id == vk_id)
                .one()
            )
        except NoResultFound:
            user_info_from_vk = await self.vk_worker.get_user_info(
                vk_id, name_case
            )
            cached_vk_user = models.CachedVKUser(
                vk_id=vk_id,
                sex=user_info_from_vk["sex"]
            )
            cached_vk_user.names = [
                models.UserNameAndSurname(
                    case=name_case,
                    name=user_info_from_vk["first_name"],
                    surname=user_info_from_vk["last_name"]
                )
            ]
            self.db_session.add(cached_vk_user)
            return cached_vk_user.get_as_vk_user_info_dataclass(name_case)
        else:
            try:
                user_info_dataclass = user_info.get_as_vk_user_info_dataclass(
                    name_case
                )
            except exceptions.NameCaseNotFound:
                user_info_from_vk = await self.vk_worker.get_user_info(
                    vk_id, name_case
                )
                user_info.names.append(
                    models.UserNameAndSurname(
                        vk_user_id=user_info.id,
                        case=name_case,
                        name=user_info_from_vk["first_name"],
                        surname=user_info_from_vk["last_name"]
                    )
                )
                return user_info.get_as_vk_user_info_dataclass(name_case)
            else:
                return user_info_dataclass

    def commit(self) -> None:
        self.db_session.commit()

    def commit_if_something_is_changed(self) -> None:
        self.db_session.commit_if_something_is_changed()

    def flush(self) -> None:
        self.db_session.flush()


class ManagersContainer:

    """
    A facade for the OrdersManager and CachedVKUsersManager.

    It is needed because managers have one session, so I can check one session
    for pending changes (otherwise, when I'm using two managers separately, I
    can't know if their sessions is the same and this is quite bad).
    """

    def __init__(
            self, orders_manager: OrdersManager,
            users_manager: CachedVKUsersManager) -> None:
        self.orders_manager = orders_manager
        self.users_manager = users_manager
        self.session_is_the_same_in_all_managers = (
            orders_manager.db_session is users_manager.db_session
        )

    def commit_if_something_is_changed(self) -> None:
        if self.session_is_the_same_in_all_managers:
            # Working with the db_session of the orders_manager because why not
            self.orders_manager.commit_if_something_is_changed()
        else:
            for manager in (self.orders_manager, self.users_manager):
                manager.commit_if_something_is_changed()

    def commit(self) -> None:
        if self.session_is_the_same_in_all_managers:
            # Working with the db_session of the orders_manager because why not
            self.orders_manager.commit()
        else:
            for manager in (self.orders_manager, self.users_manager):
                manager.commit()

    def flush(self) -> None:
        if self.session_is_the_same_in_all_managers:
            # Working with the db_session of the orders_manager because why not
            self.orders_manager.flush()
        else:
            for manager in (self.orders_manager, self.users_manager):
                manager.flush()
