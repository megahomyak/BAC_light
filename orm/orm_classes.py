from typing import List

from sqlalchemy import Column, Integer, DateTime, String, SmallInteger, \
    ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship

DeclarativeBase = declarative_base()


# noinspection PyMethodParameters
# Because when the first argument is named `cls`, class is really
# passed into it
class Order(DeclarativeBase):

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True)

    creator_vk_id = Column(Integer, nullable=False)
    text = Column(String, nullable=False)

    taker_vk_id = Column(Integer)

    canceler_vk_id = Column(Integer)
    cancellation_reason = Column(String)

    earnings = Column(Integer)
    earning_date = Column(DateTime)

    @hybrid_property
    def is_taken(self) -> bool:
        return self.taker_vk_id is not None

    @is_taken.expression
    def is_taken(cls):
        return cls.taker_vk_id.isnot(None)

    @hybrid_property
    def is_canceled(self) -> bool:
        return self.canceler_vk_id is not None

    @is_canceled.expression
    def is_canceled(cls):
        return cls.canceler_vk_id.isnot(None)

    @hybrid_property
    def is_paid(self) -> bool:
        return self.earnings is not None

    @is_paid.expression
    def is_paid(cls):
        return cls.earnings.isnot(None)


class UserNameAndSurname(DeclarativeBase):

    __tablename__ = "names_and_surnames"

    id = Column(Integer, primary_key=True)

    vk_user_id = Column(Integer, ForeignKey("vk_users.id"), nullable=False)

    case = Column(String, nullable=False)

    name = Column(String, nullable=False)
    surname = Column(String, nullable=False)

    vk_user: List["CachedVKUser"] = (
        relationship("CachedVKUser", back_populates="names")
    )


class CachedVKUser(DeclarativeBase):

    __tablename__ = "vk_users"

    id = Column(Integer, primary_key=True)
    vk_id = Column(Integer, nullable=False)

    sex = Column(SmallInteger, nullable=False)

    names: List[UserNameAndSurname] = (
        relationship("UserNameAndSurname", back_populates="vk_user")
    )
