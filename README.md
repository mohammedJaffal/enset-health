# Health Monitoring Platform

A professional, scalable health tracking application built with Django, SQLAlchemy utilities, and AI-powered insights.

## Project Structure

```
HealthTech/
├── .env                       # For DEEPSEEK_API_KEY (create manually)
├── requirements.txt           # Python dependencies
├── db.sqlite3                 # SQLite database used by Django (auto-created)
├── manage.py                  # Django management script
├── config/                    # Django project settings & URL config
├── health/                    # Django app: models, views, templates
├── models/                    # Optional SQLAlchemy utilities
├── services/                  # Business logic, DB helpers, AI service
├── templates/                 # Django templates
├── static/                    # Static assets
├── seed_django.py             # Script to seed Django DB with sample data
└── seed_database.py           # (legacy) script used before Django port
```

## Quick Start

### 1. Create and Activate Virtual Environment (Recommended)

**On Windows:**

```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment (PowerShell)
.\venv\Scripts\Activate.ps1
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Initialize Database with Sample Data

```powershell
# Run migrations
python manage.py migrate

# Seed the Django database with sample records
python seed_django.py
```

This creates 30 days of synthetic health data in the Django database (`db.sqlite3`).

### 4. Run the Django Development Server

```powershell
# Start the Django development server
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser. Use the Django admin (if enabled) at `/admin/`.

## AI Configuration (Optional)

Create a `.env` file in the project root with your API key:

```env
DEEPSEEK_API_KEY=your_actual_api_key_here
```

AI features are optional — the app works without the key, but AI endpoints will be disabled.

## Database Location

The Django SQLite database file is `db.sqlite3` in the project root. It is created when you run migrations or seed the DB.

## Development Notes

- Database operations and helper utilities live in `services/` and `models/`.
- Templates are under `templates/` and static assets under `static/`.
- Legacy Streamlit pages and helpers were removed when porting to Django.

## Technology Stack

- Backend / Web Framework: Django
- Database: SQLite (Django ORM) — `db.sqlite3`
- Utilities: SQLAlchemy helpers (optional), `services/db_service.py` for standalone scripts
- Visualization / AI / Data Processing: Plotly, Pandas, NumPy
- AI: DeepSeek API (OpenAI-compatible)

## License

HealthTech Team - 2025
