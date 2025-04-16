from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum as SQLAlchemyEnum,
    ForeignKey, Integer, String, Table, Text, Float
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


class WeekDay(str, Enum):
    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"


class TimeSlot(str, Enum):
    SLOT_8_10 = "8:00-10:00"
    SLOT_10_12 = "10:00-12:00"
    SLOT_12_14 = "12:00-14:00"
    SLOT_14_16 = "14:00-16:00"
    SLOT_16_18 = "16:00-18:00"


# Ассоциативная таблица для связи пользователей и интересов
user_topics = Table(
    "user_topics",
    Base.metadata,
    Column("user_id", BigInteger, ForeignKey("users.telegram_id"), primary_key=True),
    Column("topic", SQLAlchemyEnum(TopicType), primary_key=True),
)


# Таблица для связи пользователей и интересов (many-to-many)
user_interests = Table(
    'user_interests',
    Base.metadata,
    Column('user_id', BigInteger, ForeignKey('users.telegram_id'), primary_key=True),
    Column('interest_id', Integer, ForeignKey('interests.id'), primary_key=True)
)


class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=False)
    department = Column(String(255), nullable=True)
    role = Column(String(255), nullable=True)
    meeting_format = Column(SQLAlchemyEnum(MeetingFormat), nullable=True)
    city = Column(String(255), nullable=True)
    office = Column(String(255), nullable=True)
    available_days = Column(String(255), nullable=True)  # Хранит список дней в виде строки (разделенной запятыми)
    available_time_slot = Column(String(255), nullable=True)  # Хранит выбранный временной слот
    work_hours_start = Column(String(5), nullable=True)  # Время начала рабочего дня (формат "ЧЧ:ММ")
    work_hours_end = Column(String(5), nullable=True)  # Время окончания рабочего дня (формат "ЧЧ:ММ")
    photo_id = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    registration_complete = Column(Boolean, default=False)
    user_number = Column(Integer, nullable=True)  # Порядковый номер пользователя
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    topics = []  # TopicType это перечисление, а не класс модели
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
    interests = relationship("Interest", secondary=user_interests, back_populates="users")

    @property
    def all_meetings(self):
        """Получить все встречи пользователя"""
        return self.meetings_as_user1 + self.meetings_as_user2

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, name={self.full_name})>"


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True)
    user1_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    user2_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    scheduled_date = Column(DateTime, nullable=True)  # Переименовано с meeting_date для согласованности
    meeting_format = Column(SQLAlchemyEnum(MeetingFormat), nullable=True)
    meeting_location = Column(String(255), nullable=True)
    is_confirmed = Column(Boolean, default=False)
    is_completed = Column(Boolean, default=False)
    is_cancelled = Column(Boolean, default=False)  # Новое поле для отмененных встреч
    feedback_requested = Column(Boolean, default=False)  # Новое поле для отслеживания отправки запроса на фидбек
    reminder_sent = Column(Boolean, default=False)  # Новое поле для отслеживания отправки напоминаний
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Связи
    user1 = relationship("User", foreign_keys=[user1_id], back_populates="meetings_as_user1")
    user2 = relationship("User", foreign_keys=[user2_id], back_populates="meetings_as_user2")
    feedbacks = relationship("Feedback", back_populates="meeting")

    def __repr__(self):
        return f"<Meeting(id={self.id}, user1_id={self.user1_id}, user2_id={self.user2_id}, date={self.scheduled_date})>"


class Feedback(Base):
    __tablename__ = "feedbacks"

    id = Column(Integer, primary_key=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    from_user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    to_user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    rating = Column(Integer, nullable=True)  # 1-5
    comment = Column(Text, nullable=True)
    improvement_suggestion = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связи
    meeting = relationship("Meeting", back_populates="feedbacks")
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="feedbacks_given")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="feedbacks_received")

    def __repr__(self):
        return f"<Feedback(id={self.id}, meeting_id={self.meeting_id}, from_user_id={self.from_user_id}, rating={self.rating})>"


class Interest(Base):
    __tablename__ = "interests"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    emoji = Column(String, nullable=True)
    
    # Связь с пользователями (many-to-many)
    users = relationship("User", secondary=user_interests, back_populates="interests") 