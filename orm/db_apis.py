from typing import Any, List

from sqlalchemy.orm import Session, Query

from orm import orm_classes


class OrdersManager:

    def __init__(self, sqlalchemy_session: Session) -> None:
        self.db_session = sqlalchemy_session

    def _get_query(self) -> Query:
        return (
            self.db_session
            .query(orm_classes.Order)
        )

    def get_tasks(self, *filters: Any) -> List[orm_classes.Order]:
        return (
            self._get_query()
            .filter(*filters)
            .all()
        ) if filters else (
            self._get_query()
            .all()
        )

    def get_task_by_id(self, task_id: int) -> orm_classes.Order:
        return (
            self._get_query()
            .filter_by(id=task_id)
            .one()
        )

    def commit(self) -> None:
        self.db_session.commit()

    def delete(self, *orders: orm_classes.Order) -> None:
        for order in orders:
            self.db_session.delete(order)

    def add(self, *orders: orm_classes.Order) -> None:
        self.db_session.add_all(orders)
