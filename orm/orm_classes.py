from sqlalchemy import Column, Integer, DateTime, String, SmallInteger
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property

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


class CachedVKUser(DeclarativeBase):

    __tablename__ = "cached_vk_users"

    id = Column(Integer, primary_key=True)
    vk_id = Column(Integer, nullable=False)

    sex = Column(SmallInteger, nullable=False)

    name_nom = Column(String)
    surname_nom = Column(String)

    name_gen = Column(String)
    surname_gen = Column(String)

    name_dat = Column(String)
    surname_dat = Column(String)

    name_acc = Column(String)
    surname_acc = Column(String)

    name_ins = Column(String)
    surname_ins = Column(String)

    name_abl = Column(String)
    surname_abl = Column(String)
