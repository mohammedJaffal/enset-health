"""
Database Service - CRUD Operations for Health Records

This module provides all database operations for health records.
It replaces the CSV-based logic from data_engine.py with SQLAlchemy operations.
"""

from models.database import HealthRecord, get_session, init_database
from sqlalchemy.exc import IntegrityError
from datetime import date, datetime
from typing import List, Optional, Dict
import pandas as pd


def init_db_if_needed():
    """Initialize database if it doesn't exist."""
    init_database()


def create_record(date: date, heart_rate: int, sleep_hours: float, steps: int) -> Optional[HealthRecord]:
    """
    Create a new health record in the database.
    
    Args:
        date: Date of the record
        heart_rate: Heart rate in bpm
        sleep_hours: Hours of sleep
        steps: Number of steps
    
    Returns:
        HealthRecord: The created record, or None if creation failed
    """
    session = get_session()
    try:
        # Check if record for this date already exists
        existing = session.query(HealthRecord).filter(HealthRecord.date == date).first()
        if existing:
            print(f"[WARNING] Record for {date} already exists. Use update_record() instead.")
            session.close()
            return None
        
        record = HealthRecord(
            date=date,
            heart_rate=heart_rate,
            sleep_hours=sleep_hours,
            steps=steps
        )
        session.add(record)
        session.commit()
        session.refresh(record)
        print(f"[OK] Created record for {date}")
        return record
    except IntegrityError:
        session.rollback()
        print(f"[ERROR] Failed to create record for {date} - duplicate date")
        return None
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Failed to create record: {str(e)}")
        return None
    finally:
        session.close()


def get_record_by_date(record_date: date) -> Optional[HealthRecord]:
    """
    Get a health record by date.
    
    Args:
        record_date: Date to search for
    
    Returns:
        HealthRecord: The record if found, None otherwise
    """
    session = get_session()
    try:
        record = session.query(HealthRecord).filter(HealthRecord.date == record_date).first()
        return record
    finally:
        session.close()


def get_all_records() -> List[HealthRecord]:
    """
    Get all health records, ordered by date.
    
    Returns:
        List[HealthRecord]: List of all health records
    """
    session = get_session()
    try:
        records = session.query(HealthRecord).order_by(HealthRecord.date).all()
        return records
    finally:
        session.close()


def get_records_as_dataframe() -> pd.DataFrame:
    """
    Get all health records as a pandas DataFrame.
    
    This is useful for visualization and analysis in Streamlit.
    
    Returns:
        pd.DataFrame: DataFrame with columns: Date, Heart_Rate, Sleep_Hours, Steps
    """
    records = get_all_records()
    if not records:
        # Return empty DataFrame with correct structure
        return pd.DataFrame(columns=['Date', 'Heart_Rate', 'Sleep_Hours', 'Steps'])
    
    data = []
    for record in records:
        data.append({
            'Date': record.date,
            'Heart_Rate': record.heart_rate,
            'Sleep_Hours': record.sleep_hours,
            'Steps': record.steps
        })
    
    df = pd.DataFrame(data)
    df['Date'] = pd.to_datetime(df['Date'])
    return df


def update_record(record_date: date, heart_rate: Optional[int] = None, 
                  sleep_hours: Optional[float] = None, steps: Optional[int] = None) -> bool:
    """
    Update an existing health record.
    
    Args:
        record_date: Date of the record to update
        heart_rate: New heart rate (optional)
        sleep_hours: New sleep hours (optional)
        steps: New steps count (optional)
    
    Returns:
        bool: True if update was successful, False otherwise
    """
    session = get_session()
    try:
        record = session.query(HealthRecord).filter(HealthRecord.date == record_date).first()
        if not record:
            print(f"[ERROR] Record for {record_date} not found")
            return False
        
        if heart_rate is not None:
            record.heart_rate = heart_rate
        if sleep_hours is not None:
            record.sleep_hours = sleep_hours
        if steps is not None:
            record.steps = steps
        
        session.commit()
        print(f"[OK] Updated record for {record_date}")
        return True
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Failed to update record: {str(e)}")
        return False
    finally:
        session.close()


def delete_record(record_date: date) -> bool:
    """
    Delete a health record by date.
    
    Args:
        record_date: Date of the record to delete
    
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    session = get_session()
    try:
        record = session.query(HealthRecord).filter(HealthRecord.date == record_date).first()
        if not record:
            print(f"[ERROR] Record for {record_date} not found")
            return False
        
        session.delete(record)
        session.commit()
        print(f"[OK] Deleted record for {record_date}")
        return True
    except Exception as e:
        session.rollback()
        print(f"[ERROR] Failed to delete record: {str(e)}")
        return False
    finally:
        session.close()


def get_latest_record() -> Optional[HealthRecord]:
    """
    Get the most recent health record.
    
    Returns:
        HealthRecord: The latest record, or None if no records exist
    """
    session = get_session()
    try:
        record = session.query(HealthRecord).order_by(HealthRecord.date.desc()).first()
        return record
    finally:
        session.close()


def get_statistics() -> Dict:
    """
    Calculate and return statistics for all health records.
    
    Returns:
        dict: Dictionary with average heart_rate, sleep_hours, steps, and total_days
    """
    df = get_records_as_dataframe()
    if df.empty:
        return {
            'avg_heart_rate': 0,
            'avg_sleep': 0,
            'avg_steps': 0,
            'total_days': 0
        }
    
    return {
        'avg_heart_rate': df['Heart_Rate'].mean(),
        'avg_sleep': df['Sleep_Hours'].mean(),
        'avg_steps': df['Steps'].mean(),
        'total_days': len(df)
    }


def get_records_by_date_range(start_date: date, end_date: date) -> List[HealthRecord]:
    """
    Get health records within a date range.
    
    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)
    
    Returns:
        List[HealthRecord]: List of records in the date range
    """
    session = get_session()
    try:
        records = session.query(HealthRecord).filter(
            HealthRecord.date >= start_date,
            HealthRecord.date <= end_date
        ).order_by(HealthRecord.date).all()
        return records
    finally:
        session.close()

