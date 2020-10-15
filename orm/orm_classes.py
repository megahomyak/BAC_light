from sqlalchemy import Column, Integer, DateTime, String
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
