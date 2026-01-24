from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, DateTime
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Связь с поездками
    rides = relationship("Ride", back_populates="user", cascade="all, delete-orphan")

class Ride(Base):
    __tablename__ = "rides"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Данные маршрута
    origin = Column(String(255), nullable=False, index=True)      # Откуда
    destination = Column(String(255), nullable=False, index=True) # Куда
    
    # Время и дата
    ride_date = Column(String(100), nullable=True, index=True)    # Поле для хранения даты (напр. "2025-12-27")
    start_time = Column(String(100), nullable=True)   # Поле для хранения времени (напр. "10:00")
    
    initial_seats = Column(Integer, nullable=False)
    seats = Column(Integer, nullable=False)
    role = Column(String(50))                         # driver или passenger
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="rides")

class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True)
    driver_ride_id = Column(Integer, ForeignKey("rides.id"))
    passenger_ride_id = Column(Integer, ForeignKey("rides.id"))
    status = Column(String(50), default='pending')    # pending, confirmed, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
