"""
Django Seed Script - Generate Dummy Health Data

This script generates synthetic health data and populates the Django database.
Run this after creating migrations: python manage.py migrate
"""

import os
import django
import numpy as np
from datetime import datetime, timedelta

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from health.models import HealthRecord


def generate_dummy_data(days=30):
    """
    Generate synthetic health monitoring data for the specified number of days.
    
    Args:
        days (int): Number of days of data to generate (default: 30)
    """
    # Set random seed for reproducibility
    np.random.seed(42)
    
    # Check if database already has data
    existing_count = HealthRecord.objects.count()
    if existing_count > 0:
        print(f"[WARNING] Database already contains {existing_count} records.")
        response = input("Do you want to continue? This may create duplicates. (y/n): ")
        if response.lower() != 'y':
            print("[INFO] Seed cancelled.")
            return 0
    
    # Calculate the date range: from (days) days ago to today
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days - 1)
    
    print(f"[INFO] Generating {days} days of health data...")
    print(f"  Date range: {start_date} to {end_date}")
    
    created_count = 0
    skipped_count = 0
    
    # Generate data for each day
    current_date = start_date
    while current_date <= end_date:
        # Heart Rate: Base range 60-100, with 10% chance of spike (110-130)
        if np.random.random() < 0.1:  # 10% chance of spike
            heart_rate = np.random.randint(110, 131)  # Spike range
        else:
            heart_rate = np.random.randint(60, 101)  # Normal range
        
        # Sleep Hours: Random float between 4.0 and 9.0
        sleep_hours = round(np.random.uniform(4.0, 9.0), 1)
        
        # Steps: Random integer between 2000 and 15000
        steps = np.random.randint(2000, 15001)
        
        # Create record in database
        record, created = HealthRecord.objects.get_or_create(
            date=current_date,
            defaults={
                'heart_rate': heart_rate,
                'sleep_hours': sleep_hours,
                'steps': steps
            }
        )
        
        if created:
            created_count += 1
        else:
            skipped_count += 1
        
        # Move to next day
        current_date += timedelta(days=1)
    
    print("\n" + "=" * 60)
    print(f"[OK] Data generation completed!")
    print(f"  Created: {created_count} records")
    if skipped_count > 0:
        print(f"  Skipped (duplicates): {skipped_count} records")
    print("=" * 60)
    
    return created_count


if __name__ == "__main__":
    print("=" * 60)
    print("Health Monitoring Platform - Django Seed Script")
    print("=" * 60)
    print()
    
    # Generate 30 days of data
    generate_dummy_data(days=30)
    
    # Display summary
    total_records = HealthRecord.objects.count()
    print(f"\n[INFO] Total records in database: {total_records}")

