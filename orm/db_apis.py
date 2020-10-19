from typing import Any, List

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, Query
from sqlalchemy.orm.exc import NoResultFound

import exceptions
from orm import models
from vk import dataclasses_
from vk.enums import NameCases
from vk.vk_worker import VKWorker


def get_sqlalchemy_db_session(path_to_sqlite_db: str) -> Session:
    sql_engine = create_engine(path_to_sqlite_db)
    models.DeclarativeBase.metadata.create_all(sql_engine)
    return Session(sql_engine)


class OrdersManager:

    def __init__(self, sqlalchemy_session: Session) -> None:
        self.db_session = sqlalchemy_session

    def _get_query(self) -> Query:
        return (
            self.db_session
            .query(models.Order)
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
            self._get_query()
            .filter_by(id=order_id)
            .one()
        )

    def commit(self) -> None:
        self.db_session.commit()

    def delete(self, *orders: models.Order) -> None:
        for order in orders:
            self.db_session.delete(order)

    def add(self, *orders: models.Order) -> None:
        self.db_session.add_all(orders)


class CachedVKUsersManager:

    def __init__(
            self, sqlalchemy_session: Session,
            vk_worker: VKWorker) -> None:
        self.db_session = sqlalchemy_session
        self.vk_worker = vk_worker

    async def get_user_info_by_id(
            self, vk_id: int,
            name_case: NameCases = NameCases.NOM
            ) -> dataclasses_.RequestedVKUserInfo:
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
            user_info = models.CachedVKUser(
                vk_id=vk_id,
                sex=user_info_from_vk["sex"]
            )
            self.db_session.flush()
            self.db_session.add_all(
                (
                    models.UserNameAndSurname(
                        vk_user_id=user_info.id,
                        case=name_case,
                        name=user_info_from_vk["first_name"],
                        surname=user_info_from_vk["last_name"]
                    ),
                    user_info
                )
            )
            return dataclasses_.RequestedVKUserInfo(
                user_info.get_as_vk_user_info_dataclass(name_case),
                is_downloaded=True
            )
        else:
            try:
                user_info_dataclass = user_info.get_as_vk_user_info_dataclass(
                    name_case
                )
            except exceptions.NameCaseNotFound:
                user_info_from_vk = await self.vk_worker.get_user_info(
                    vk_id, name_case
                )
                self.db_session.add(
                    models.UserNameAndSurname(
                        vk_user_id=user_info.id,
                        case=name_case,
                        name=user_info_from_vk["first_name"],
                        surname=user_info_from_vk["last_name"]
                    )
                )
                return dataclasses_.RequestedVKUserInfo(
                    user_info.get_as_vk_user_info_dataclass(name_case),
                    is_downloaded=True
                )
            else:
                return dataclasses_.RequestedVKUserInfo(
                    user_info_dataclass,
                    is_downloaded=False
                )

    def commit(self) -> None:
        self.db_session.commit()
