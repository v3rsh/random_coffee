from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum as SQLAlchemyEnum,
    ForeignKey, Integer, String, Table, Text
)
from sqlalchemy.orm import relationship, DeclarativeBase


class Base(DeclarativeBase):
    pass


class MeetingFormat(str, Enum):
    OFFLINE = "offline"
    ONLINE = "online"
    ANY = "any"


class TopicType(str, Enum):
    PRODUCT_DEVELOPMENT = "product_development"
    HOBBIES = "hobbies"
    LANGUAGES = "languages"
    GENERAL_CHAT = "general_chat"


# Ассоциативная таблица для связи пользователей и интересов
user_topics = Table(
    "user_topics",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.telegram_id"), primary_key=True),
    Column("topic", SQLAlchemyEnum(TopicType), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=False)
    department = Column(String(255), nullable=True)
    work_hours_start = Column(String(5), nullable=True)  # Формат "HH:MM"
    work_hours_end = Column(String(5), nullable=True)  # Формат "HH:MM"
    meeting_format = Column(SQLAlchemyEnum(MeetingFormat), default=MeetingFormat.ANY)
    is_active = Column(Boolean, default=True)
    registration_complete = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    topics = relationship("TopicType", secondary=user_topics, backref="users")
    meetings_as_user1 = relationship(
        "Meeting", foreign_keys="Meeting.user1_id", back_populates="user1"
    )
    meetings_as_user2 = relationship(
        "Meeting", foreign_keys="Meeting.user2_id", back_populates="user2"
    )
    feedbacks_given = relationship(
        "Feedback", foreign_keys="Feedback.from_user_id", back_populates="from_user"
    )
    feedbacks_received = relationship(
        "Feedback", foreign_keys="Feedback.to_user_id", back_populates="to_user"
    )

    @property
    def all_meetings(self):
        """Получить все встречи пользователя"""
        return self.meetings_as_user1 + self.meetings_as_user2


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True)
    user1_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    user2_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    scheduled_date = Column(DateTime, nullable=True)
    is_confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    user1 = relationship("User", foreign_keys=[user1_id], back_populates="meetings_as_user1")
    user2 = relationship("User", foreign_keys=[user2_id], back_populates="meetings_as_user2")
    feedbacks = relationship("Feedback", back_populates="meeting")


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    from_user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    to_user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    rating = Column(Integer, nullable=True)  # 1-5
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    meeting = relationship("Meeting", back_populates="feedbacks")
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="feedbacks_given")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="feedbacks_received") 