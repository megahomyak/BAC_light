from typing import Any, List

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, Query

from orm import orm_classes


def get_sqlalchemy_db_session(path_to_sqlite_db: str) -> Session:
    sql_engine = create_engine(path_to_sqlite_db)
    orm_classes.DeclarativeBase.metadata.create_all(sql_engine)
    return Session(sql_engine)


class OrdersManager:

    def __init__(self, sqlalchemy_session: Session) -> None:
        self.db_session = sqlalchemy_session

    def _get_query(self) -> Query:
        return (
            self.db_session
            .query(orm_classes.Order)
        )

    def get_orders(self, *filters: Any) -> List[orm_classes.Order]:
        return (
            self._get_query()
            .filter(*filters)
            .all()
        ) if filters else (
            self._get_query()
            .all()
        )

    def get_order_by_id(self, order_id: int) -> orm_classes.Order:
        return (
            self._get_query()
            .filter_by(id=order_id)
            .one()
        )

    def commit(self) -> None:
        self.db_session.commit()

    def delete(self, *orders: orm_classes.Order) -> None:
        for order in orders:
            self.db_session.delete(order)

    def add(self, *orders: orm_classes.Order) -> None:
        self.db_session.add_all(orders)
