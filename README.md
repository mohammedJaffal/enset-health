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

### ⚠️ Important Prerequisites

The application uses a SQLite database stored in a `data/` directory. This directory **must be created** before running migrations.

### 1. Activate Virtual Environment (Recommended)

**On Windows (PowerShell):**

```powershell
# Navigate to the project directory
cd path\to\enset-health

# Activate virtual environment
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\venv\Scripts\Activate.ps1

# You should see (venv) at the start of your prompt
```

**On Windows (Command Prompt):**

```cmd
cd path\to\enset-health
.\venv\Scripts\activate.bat
```

### 2. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 3. Create the Data Directory

**⚠️ This step is CRITICAL and often missed!** The application expects a `data/` directory for the SQLite database.

```powershell
# Create the data directory (from project root)
mkdir data
```

If the directory already exists, you can skip this step.

### 4. Initialize Database with Migrations and Sample Data

```powershell
# Run Django migrations (creates database schema)
python manage.py migrate

# Seed the database with 30 days of synthetic health data
python seed_django.py
```

This will create `data/health.db` with all necessary tables and sample records.

**Expected Output:**
```
============================================================
Health Monitoring Platform - Django Seed Script
============================================================

[INFO] Generating 30 days of health data...
  Date range: 2025-12-08 to 2026-01-06

[OK] Data generation completed!
  Created: 30 records
```

### 5. Run the Django Development Server

```powershell
python manage.py runserver
```

Open http://127.0.0.1:8000/ in your browser.

### Scheduled Email Reports

- Configure cadence under **Settings → Report Scheduling** (daily/weekly/monthly, time of day, and recipient).
- Set email credentials in `.env` (SMTP host, user, password, `DEFAULT_FROM_EMAIL`, optional `REPORT_RECIPIENT_FALLBACK`).
- Use Task Scheduler/cron to run `python manage.py send_scheduled_reports` at least hourly to deliver due PDFs.

## AI Configuration (Optional)

AI features are optional — the app works without configuration, but AI endpoints will be disabled.

To enable AI features:

1. Get your API key from [DeepSeek](https://www.deepseek.com/)
2. Copy `.env.example` to `.env`:

```powershell
copy .env.example .env
```

3. Edit `.env` and add your API key:

```env
DEEPSEEK_API_KEY=your_actual_api_key_here
```

The application will automatically load environment variables from the `.env` file.

## Database Location

The Django SQLite database file is `data/health.db`. It is created when you run migrations. The `data/` directory must exist before running migrations.

## Troubleshooting

### Error: "unable to open database file"

This error typically occurs when the `data/` directory doesn't exist.

**Solution:**
```powershell
mkdir data
python manage.py migrate
```

### Virtual Environment Not Activating

If your shell doesn't recognize the activate command, try using the full path:

**Windows PowerShell:**
```powershell
& ".\venv\Scripts\Activate.ps1"
```

**Windows Command Prompt:**
```cmd
.\venv\Scripts\activate.bat
```

### Port 8000 Already in Use

If port 8000 is already in use, run the server on a different port:

```powershell
python manage.py runserver 8001
```

Then access the app at http://127.0.0.1:8001/

### Missing Dependencies

If you get import errors, reinstall dependencies:

```powershell
pip install -r requirements.txt --upgrade
```

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
