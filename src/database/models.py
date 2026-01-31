from sqlalchemy import Column, Integer, BigInteger, String, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from .session import Base


class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    rides = relationship("Ride", back_populates="user")
    bookings = relationship("Booking", back_populates="passenger")
    
    def __repr__(self):
        return f"User(id={self.id}, telegram_id={self.telegram_id}, username={self.username})"


class Ride(Base):
    __tablename__ = "rides"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    role = Column(String, nullable=False)
    origin = Column(String, nullable=False)
    destination = Column(String, nullable=False)
    ride_date = Column(Date, nullable=False)  # ← DATE вместо String
    start_time = Column(String, nullable=True)
    initial_seats = Column(Integer, nullable=True)
    seats = Column(Integer, default=1)
    raw_text = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    user = relationship("User", back_populates="rides")
    bookings = relationship("Booking", back_populates="ride")
    
    def __repr__(self):
        return f"Ride(id={self.id}, role={self.role}, {self.origin}->{self.destination})"


class Booking(Base):
    __tablename__ = "bookings"
    
    id = Column(Integer, primary_key=True, index=True)
    driver_ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    passenger_ride_id = Column(Integer, ForeignKey("rides.id"), nullable=False)
    status = Column(String, default='pending')
    created_at = Column(DateTime, default=datetime.now)
    
    # Relationships
    ride = relationship("Ride", foreign_keys=[driver_ride_id], back_populates="bookings")
    passenger = relationship("User", back_populates="bookings")
    
    def __repr__(self):
        return f"Booking(id={self.id}, driver_ride_id={self.driver_ride_id}, status={self.status})"
