from typing import Any, List

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, Query
from sqlalchemy.orm.exc import NoResultFound

import exceptions
from orm import models
from vk import vk_related_classes
from vk.enums import NameCases
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

    def get_order_by_id(self, order_id: int) -> models.Order:
        return (
            self.db_session
            .query(models.Order)
            .filter_by(id=order_id)
            .one()
        )

    def commit(self) -> None:
        self.db_session.commit()

    def commit_if_something_is_changed(self) -> None:
        self.db_session.commit_if_something_is_changed()

    def delete(self, *orders: models.Order) -> None:
        for order in orders:
            self.db_session.delete(order)

    def add(self, *orders: models.Order) -> None:
        self.db_session.add_all(orders)


class CachedVKUsersManager:

    def __init__(
            self, sqlalchemy_session: MySession,
            vk_worker: VKWorker) -> None:
        self.db_session = sqlalchemy_session
        self.vk_worker = vk_worker

    async def get_user_info_by_id(
            self, vk_id: int,
            name_case: NameCases = NameCases.NOM
            ) -> vk_related_classes.VKUserInfo:
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
            self.db_session.add(
                cached_vk_user
            )
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
