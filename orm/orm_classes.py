from sqlalchemy import Column, Integer, DateTime, String
from sqlalchemy.ext.declarative import declarative_base

DeclarativeBase = declarative_base()


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
