from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Date, ForeignKey, func
from sqlalchemy.orm import relationship
from datetime import datetime
from .session import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    rides = relationship("Ride", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.telegram_id}>"


class Ride(Base):
    __tablename__ = "rides"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)  # "driver" или "passenger"
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    date = Column(Date, nullable=False)  # Тип Date для PostgreSQL
    start_time = Column(String, nullable=True)
    seats = Column(Integer, default=1)
    raw_text = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # Relationships
    user = relationship("User", back_populates="rides")

    def __repr__(self):
        return f"<Ride {self.origin} → {self.destination}>"


class Booking(Base):
    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, index=True)
    driver_ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    passenger_ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    status = Column(String, default="pending")  # pending, confirmed, cancelled
    created_at = Column(DateTime, default=func.now())

    def __repr__(self):
        return f"<Booking driver_ride={self.driver_ride_id} passenger_ride={self.passenger_ride_id}>"