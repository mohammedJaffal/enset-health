"""
Utility Functions for Health Monitoring Platform

This module contains reusable utility functions for health data analysis.
"""

from typing import Dict, Optional
import pandas as pd

# Try to import Django model, fallback to SQLAlchemy for backward compatibility
try:
    from health.models import HealthRecord as DjangoHealthRecord
    DJANGO_AVAILABLE = True
except ImportError:
    DJANGO_AVAILABLE = False
    try:
        from models.database import HealthRecord as SQLAlchemyHealthRecord
        from services.db_service import get_latest_record, get_all_records
    except ImportError:
        pass


def check_latest_alerts(record=None) -> Dict:
    """
    Check if the latest day's data has any health alerts.
    
    Works with both Django and SQLAlchemy models.
    
    Args:
        record: Optional HealthRecord to check. If None, fetches latest from DB.
    
    Returns:
        dict: Dictionary with alert status and messages
    """
    if record is None:
        if DJANGO_AVAILABLE:
            record = DjangoHealthRecord.objects.first()
        else:
            record = get_latest_record()
    
    if record is None:
        return {
            'has_alert': False,
            'messages': []
        }
    
    alerts = {
        'has_alert': False,
        'messages': []
    }
    
    # Check for high heart rate (> 110 bpm)
    if record.heart_rate > 110:
        alerts['has_alert'] = True
        alerts['messages'].append(f"⚠️ High Heart Rate: {record.heart_rate} bpm (normal: ≤110)")
    
    # Check for low sleep (< 5 hours)
    if record.sleep_hours < 5.0:
        alerts['has_alert'] = True
        alerts['messages'].append(f"⚠️ Low Sleep: {record.sleep_hours} hours (normal: ≥5.0)")
    
    return alerts


def check_alerts_for_record(record) -> Dict:
    """
    Check alerts for a specific health record.
    
    Args:
        record: HealthRecord to check
    
    Returns:
        dict: Dictionary with alert status and messages
    """
    return check_latest_alerts(record)


def get_alert_days() -> pd.DataFrame:
    """
    Get all days that have health alerts (high heart rate or low sleep).
    
    Returns:
        pd.DataFrame: DataFrame containing only alert days
    """
    if DJANGO_AVAILABLE:
        records = DjangoHealthRecord.objects.all()
    else:
        records = get_all_records()
    
    if not records:
        return pd.DataFrame(columns=['Date', 'Heart_Rate', 'Sleep_Hours', 'Steps'])
    
    alert_records = []
    for record in records:
        if record.heart_rate > 110 or record.sleep_hours < 5.0:
            alert_records.append({
                'Date': record.date,
                'Heart_Rate': record.heart_rate,
                'Sleep_Hours': record.sleep_hours,
                'Steps': record.steps
            })
    
    df = pd.DataFrame(alert_records)
    if not df.empty:
        df['Date'] = pd.to_datetime(df['Date'])
    
    return df


def calculate_metrics(df: pd.DataFrame) -> Dict:
    """
    Calculate key health metrics from a DataFrame.
    
    Args:
        df: DataFrame with health data
    
    Returns:
        dict: Dictionary containing calculated metrics
    """
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

