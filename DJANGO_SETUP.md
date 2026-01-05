# Django Setup Guide

The application has been migrated from Streamlit to Django. Follow these steps to get started.

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Migrations

The database migrations have already been created. If you need to recreate them:

```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Create Superuser (Optional)

To access the Django admin panel:

```bash
python manage.py createsuperuser
```

### 4. Seed Database (Optional)

Generate sample data:

```bash
python seed_django.py
```

### 5. Run Development Server

```bash
python manage.py runserver
```

The application will be available at `http://127.0.0.1:8000/`

## Project Structure

```
HealthTech/
├── config/              # Django project settings
│   ├── settings.py     # Main settings file
│   ├── urls.py         # Root URL configuration
│   └── wsgi.py         # WSGI configuration
├── health/              # Main Django app
│   ├── models.py       # HealthRecord model
│   ├── views.py        # View functions
│   ├── urls.py         # App URL patterns
│   └── admin.py        # Admin configuration
├── templates/           # HTML templates
│   ├── base.html       # Base template
│   └── health/         # App-specific templates
├── static/              # Static files (CSS, JS, images)
├── services/            # Business logic services
│   ├── ai_service.py   # AI integration
│   ├── db_service.py   # Database operations (legacy)
│   └── utils.py        # Utility functions
└── data/               # Database file location
    └── health.db       # SQLite database
```

## URLs

- `/` - Dashboard
- `/log-data/` - Add/View health records
- `/edit/<id>/` - Edit a record
- `/delete/<id>/` - Delete a record
- `/ai-doctor/` - AI health insights
- `/admin/` - Django admin panel

## Database

The application uses SQLite database located at `data/health.db`. This is the same database used by the previous Streamlit version, so your existing data is preserved.

## Features

- ✅ Dashboard with health metrics and charts
- ✅ Add/Edit/Delete health records
- ✅ AI-powered health insights (requires DEEPSEEK_API_KEY)
- ✅ Django admin interface
- ✅ Modern dark theme UI

## Notes

- The `services/` directory still contains legacy SQLAlchemy code for backward compatibility
- The Django model (`health.models.HealthRecord`) is the primary data model
- AI service works with both Django and SQLAlchemy models

