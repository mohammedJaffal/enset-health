import logging
from typing import Tuple

from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.test.client import RequestFactory
from django.utils import timezone
from django.utils.text import slugify

from .views import get_report_data

logger = logging.getLogger(__name__)


def build_report_context(user, report_data, generated_on=None):
    """
    Build the template context for the PDF/email report.
    """
    user_display = user.get_full_name().strip() or user.get_username()
    date_range = f"{report_data['start_date'].strftime('%b %d, %Y')} - {report_data['end_date'].strftime('%b %d, %Y')}"
    generated_on_display = (generated_on or timezone.localtime()).strftime('%b %d, %Y %H:%M')

    return {
        'user_name': user_display,
        'date_range': date_range,
        'has_data': report_data['has_data'],
        'stats': report_data['stats'],
        'total_days': report_data['total_days'],
        'high_hr_days': report_data['high_hr_days'],
        'low_sleep_days': report_data['low_sleep_days'],
        'alert_days': report_data['alert_days'],
        'latest_record': report_data['latest_record'],
        'chart_images': report_data['chart_images'],
        'last_7_records': report_data['last_7_records'],
        'highlight_high_hr': report_data['highlight_high_hr'],
        'highlight_low_sleep': report_data['highlight_low_sleep'],
        'insights': report_data['insights'],
        'generated_on_display': generated_on_display,
        'kpi_hints': report_data['kpi_hints'],
        'exec_summary': report_data['exec_summary'],
    }


def generate_report_pdf_bytes(user, range_days=30) -> Tuple[bytes, str, dict]:
    """
    Render the health report PDF for a user.
    """
    try:
        from weasyprint import HTML
    except Exception as exc:  # pragma: no cover - optional dependency
        logger.error('WeasyPrint is required for PDF generation: %s', exc)
        raise

    factory = RequestFactory()
    request = factory.get('/reports/health/pdf/', {'days': range_days})
    request.user = user

    report_data = get_report_data(request)
    context = build_report_context(user, report_data)

    html = render_to_string('reports/health_report.html', context)
    base_url = settings.BASE_DIR.as_posix()
    pdf = HTML(string=html, base_url=base_url).write_pdf()

    filename_date = report_data['end_date'].strftime('%Y%m%d')
    filename = f"health_report_{slugify(user.get_username()) or 'user'}_{filename_date}.pdf"
    return pdf, filename, context


def send_report_email(user, recipient_email, range_days=30):
    """
    Generate and email the health report PDF to the recipient.
    """
    pdf_bytes, filename, context = generate_report_pdf_bytes(user, range_days=range_days)
    subject = f"Your Health Report ({context['date_range']})"
    body = render_to_string(
        'health/email/report_email.txt',
        {
            'user': user,
            'date_range': context['date_range'],
            'generated_on': context['generated_on_display'],
            'range_days': range_days,
        },
    )

    from_email = settings.DEFAULT_FROM_EMAIL or settings.EMAIL_HOST_USER
    email = EmailMessage(subject, body, from_email, [recipient_email])
    email.attach(filename, pdf_bytes, 'application/pdf')
    email.send(fail_silently=False)
    logger.info('Sent scheduled report to %s', recipient_email)
    return True
