from sqlalchemy import Column, Integer, String, BigInteger, ForeignKey, DateTime, Date  # <-- Добавили Date
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    rides = relationship("Ride", back_populates="user", cascade="all, delete-orphan")

class Ride(Base):
    __tablename__ = "rides"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    origin = Column(String(255), nullable=False, index=True)
    destination = Column(String(255), nullable=False, index=True)
    
    # ИЗМЕНЕНИЕ: Тип Date вместо String
    ride_date = Column(Date, nullable=False, index=True) 
    
    start_time = Column(String(100), nullable=True)
    
    initial_seats = Column(Integer, nullable=False)
    seats = Column(Integer, nullable=False)
    role = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="rides")

class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True)
    driver_ride_id = Column(Integer, ForeignKey("rides.id"))
    passenger_ride_id = Column(Integer, ForeignKey("rides.id"))
    status = Column(String(50), default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
