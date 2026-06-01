from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Date, ForeignKey, func, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from .session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    rides = relationship("Ride", back_populates="user", cascade="all, delete-orphan", lazy="selectin")
    delivery_requests = relationship("DeliveryRequest", back_populates="user", cascade="all, delete-orphan", foreign_keys="DeliveryRequest.user_id", lazy="selectin")
    delivery_offers = relationship("DeliveryOffer", back_populates="user", cascade="all, delete-orphan", foreign_keys="DeliveryOffer.user_id", lazy="selectin")

    def __repr__(self):
        return f"<User {self.telegram_id}>"


class Ride(Base):
    __tablename__ = "rides"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    origin = Column(String(255), nullable=False, index=True)
    destination = Column(String(255), nullable=False, index=True)

    date = Column(Date, nullable=True, index=True)
    start_time = Column(String(100), nullable=True)

    initial_seats = Column(Integer, nullable=True)
    seats = Column(Integer, nullable=False, default=1)
    role = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="rides", lazy="selectin")
    driver_bookings = relationship("Booking", foreign_keys="[Booking.driver_ride_id]", back_populates="driver_ride", lazy="selectin")
    passenger_bookings = relationship("Booking", foreign_keys="[Booking.passenger_ride_id]", back_populates="passenger_ride", lazy="selectin")

    def __repr__(self):
        return f"Ride(id={self.id}, role={self.role}, {self.origin}->{self.destination})"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True)
    driver_ride_id = Column(Integer, ForeignKey("rides.id"))
    passenger_ride_id = Column(Integer, ForeignKey("rides.id"))
    status = Column(String(50), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)

    driver_ride = relationship("Ride", foreign_keys=[driver_ride_id], back_populates="driver_bookings", lazy="selectin")
    passenger_ride = relationship("Ride", foreign_keys=[passenger_ride_id], back_populates="passenger_bookings", lazy="selectin")


# ============================================================
# МОДЕЛИ ДОСТАВКИ (Delivery Module)
# ============================================================

class DeliveryRequest(Base):
    """
    Заявка «Привези» от заказчика.
    Пользователь просит привезти товары из магазина.
    """
    __tablename__ = "delivery_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    store = Column(String(255), nullable=False, index=True)
    request_text = Column(Text, nullable=False, default="")

    desired_date = Column(String(100), nullable=True, index=True)
    desired_time_text = Column(String(100), nullable=True)

    status = Column(String(50), default='active', index=True)
    max_price = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="delivery_requests", foreign_keys=[user_id], lazy="selectin")
    matches = relationship("DeliveryMatch", back_populates="request", cascade="all, delete-orphan", foreign_keys="DeliveryMatch.request_id", lazy="selectin")

    def __repr__(self):
        return f"<DeliveryRequest(id={self.id}, store={self.store}, status={self.status})>"


class DeliveryOffer(Base):
    """
    Предложение «Привезу» от исполнителя.
    Пользователь едет в магазин и готов взять заказы.
    """
    __tablename__ = "delivery_offers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    store = Column(String(255), nullable=False, index=True)
    comment = Column(Text, nullable=True)

    trip_date = Column(String(100), nullable=True, index=True)
    trip_time = Column(String(100), nullable=True)

    capacity = Column(Integer, default=1, nullable=False)
    orders_taken = Column(Integer, default=0, nullable=False)

    status = Column(String(50), default='active', index=True)

    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="delivery_offers", foreign_keys=[user_id], lazy="selectin")
    matches = relationship("DeliveryMatch", back_populates="offer", cascade="all, delete-orphan", foreign_keys="DeliveryMatch.offer_id", lazy="selectin")

    def __repr__(self):
        return f"<DeliveryOffer(id={self.id}, store={self.store}, capacity={self.capacity})>"


class DeliveryMatch(Base):
    """
    Связка между заявкой (DeliveryRequest) и предложением (DeliveryOffer).
    Создаётся при автоматическом или ручном сопоставлении.
    """
    __tablename__ = "delivery_matches"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(Integer, ForeignKey("delivery_requests.id"), nullable=False)
    offer_id = Column(Integer, ForeignKey("delivery_offers.id"), nullable=False)

    status = Column(String(50), default='pending', index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    confirmed_at = Column(DateTime, nullable=True)

    request = relationship("DeliveryRequest", back_populates="matches", foreign_keys=[request_id], lazy="selectin")
    offer = relationship("DeliveryOffer", back_populates="matches", foreign_keys=[offer_id], lazy="selectin")

    def __repr__(self):
        return f"<DeliveryMatch(request={self.request_id}, offer={self.offer_id}, status={self.status})>"
