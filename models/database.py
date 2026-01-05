"""
Database Models for Health Monitoring Platform

This module defines the SQLAlchemy models for the health tracking database.
"""

from sqlalchemy import create_engine, Column, Integer, Float, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Base class for declarative models
Base = declarative_base()


class HealthRecord(Base):
    """
    SQLAlchemy model for health records.
    
    This model represents a single day's health data with:
    - date: The date of the record
    - heart_rate: Heart rate in beats per minute
    - sleep_hours: Hours of sleep (float)
    - steps: Number of steps taken
    """
    __tablename__ = 'health_records'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    heart_rate = Column(Integer, nullable=False)
    sleep_hours = Column(Float, nullable=False)
    steps = Column(Integer, nullable=False)
    
    def __repr__(self):
        return f"<HealthRecord(date={self.date}, heart_rate={self.heart_rate}, sleep_hours={self.sleep_hours}, steps={self.steps})>"
    
    def to_dict(self):
        """Convert record to dictionary for easy serialization."""
        return {
            'id': self.id,
            'date': self.date.isoformat() if self.date else None,
            'heart_rate': self.heart_rate,
            'sleep_hours': self.sleep_hours,
            'steps': self.steps
        }


# Database configuration
def get_database_path():
    """Get the path to the SQLite database file."""
    # Get the project root directory (parent of models/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'data', 'health.db')
    return db_path


def get_engine():
    """
    Create and return a SQLAlchemy engine for the database.
    
    Returns:
        sqlalchemy.engine.Engine: Database engine
    """
    db_path = get_database_path()
    # Ensure the data directory exists
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    # Create SQLite database URL
    db_url = f"sqlite:///{db_path}"
    engine = create_engine(db_url, echo=False, connect_args={"check_same_thread": False})
    return engine


def get_session():
    """
    Create and return a database session.
    
    Returns:
        sqlalchemy.orm.Session: Database session
    """
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def init_database():
    """
    Initialize the database by creating all tables.
    
    This should be called once to set up the database schema.
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    print(f"[OK] Database initialized at: {get_database_path()}")


if __name__ == "__main__":
    # Initialize database when run directly
    init_database()

