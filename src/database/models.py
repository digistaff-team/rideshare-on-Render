from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class Ride(Base):
    __tablename__ = "rides"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    origin = Column(String)
    destination = Column(String)
    ride_date = Column(Date)  # ← Date вместо String
    start_time = Column(String, nullable=True)
    initial_seats = Column(Integer, nullable=True)
    seats = Column(Integer)
    role = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)


class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    driver_ride_id = Column(Integer, ForeignKey("rides.id"))
    passenger_ride_id = Column(Integer, ForeignKey("rides.id"))
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow)
