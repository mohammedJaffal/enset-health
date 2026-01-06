from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse, QueryDict
from django.db.models import Avg, Count, Q
from django.utils import timezone
from django.utils.text import slugify
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from datetime import date, timedelta, datetime
from io import BytesIO
import base64
import logging
from .models import HealthRecord, Profile
from .forms import HealthRecordForm, RegistrationForm, UserSettingsForm, ProfileForm
from services.ai_service import get_ai_insights, get_ai_client
from services.utils import check_latest_alerts
import pandas as pd
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully.')
            return redirect('health:dashboard')
    else:
        form = RegistrationForm()

    return render(request, 'health/register.html', {'form': form})


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except ValueError:
        return None


def _parse_range_param(value, allowed, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed in allowed else default


def _chart_payload(records, value_field):
    if not records.exists():
        return {'dates': [], 'values': []}
    df = pd.DataFrame(list(records.values('date', value_field)))
    df['date'] = pd.to_datetime(df['date'])
    return {
        'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
        'values': df[value_field].tolist(),
    }


def _get_table_records(all_records, table_range, today):
    if table_range == 'all':
        return all_records.order_by('-date')
    table_start = today - timedelta(days=table_range - 1)
    return all_records.filter(date__gte=table_start, date__lte=today).order_by('-date')


def _build_table_links(request, hr_range, sleep_range, kpi_range):
    base = QueryDict(mutable=True)
    base['hr_range'] = hr_range
    base['sleep_range'] = sleep_range
    base['kpi_range'] = kpi_range
    search_query = request.GET.get('q')
    if search_query:
        base['q'] = search_query
    links = {}
    for value in ('7', '30', 'all'):
        params = base.copy()
        params['table_range'] = value
        links[value] = f"?{params.urlencode()}"
    return links


def _build_metric_chart(records, values, title, color, y_label):
    if not records:
        return None

    dates = [record.date.strftime('%b %d') for record in records]
    x_positions = list(range(len(dates)))

    def _svg_fallback():
        try:
            width, height = 900, 300
            margin = 50
            min_val = min(values)
            max_val = max(values)
            if max_val == min_val:
                max_val = min_val + 1

            def scale_y(val):
                return margin + (height - 2 * margin) * (1 - (val - min_val) / (max_val - min_val))

            n = len(values)
            if n == 1:
                x_positions = [width // 2]
            else:
                step = (width - 2 * margin) / (n - 1)
                x_positions = [margin + i * step for i in range(n)]

            points = " ".join([f"{x:.2f},{scale_y(v):.2f}" for x, v in zip(x_positions, values)])

            svg = f"""<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' viewBox='0 0 {width} {height}'>
                <rect x='0' y='0' width='{width}' height='{height}' fill='white' />
                <line x1='{margin}' y1='{height - margin}' x2='{width - margin}' y2='{height - margin}' stroke='#cfd8e3' stroke-width='1'/>
                <line x1='{margin}' y1='{margin}' x2='{margin}' y2='{height - margin}' stroke='#cfd8e3' stroke-width='1'/>
                <polyline points='{points}' fill='none' stroke='black' stroke-width='2' />
                <circle cx='{x_positions[0]:.2f}' cy='{scale_y(values[0]):.2f}' r='3' fill='black' />
                <circle cx='{x_positions[-1]:.2f}' cy='{scale_y(values[-1]):.2f}' r='3' fill='black' />
                </svg>"""
            return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
        except Exception as exc:
            logger.exception('Chart render failed in SVG fallback: %s: %s', type(exc).__name__, exc)
            return None

    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        fig, ax = plt.subplots(figsize=(7.2, 2.2))
        ax.plot(x_positions, values, linewidth=2.2, color=color, alpha=0.9, marker='o', markersize=3, markerfacecolor=color)
        ax.set_title(title, fontsize=10, loc='left', pad=6)
        ax.set_ylabel(y_label, fontsize=8)
        ax.tick_params(axis='both', labelsize=7)
        ax.grid(True, axis='y', alpha=0.25, color='#cfd8e3')
        ax.set_facecolor('#ffffff')
        for spine in ['top', 'right']:
            ax.spines[spine].set_visible(False)

        # Reduce tick clutter
        max_ticks = 6
        step = max(1, len(dates) // max_ticks)
        ticks = list(range(0, len(dates), step))
        if ticks[-1] != len(dates) - 1:
            ticks.append(len(dates) - 1)
        ax.set_xticks(ticks)
        ax.set_xticklabels([dates[i] for i in ticks], rotation=25, ha='right', fontsize=7)

        fig.tight_layout(pad=0.6)

        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=220, bbox_inches='tight', facecolor='white')
        plt.close(fig)
        buffer.seek(0)
        return f"data:image/png;base64,{base64.b64encode(buffer.read()).decode('ascii')}"
    except ModuleNotFoundError as exc:
        logger.warning('Matplotlib unavailable, falling back to SVG chart: %s: %s', type(exc).__name__, exc)
        return _svg_fallback()
    except Exception as exc:
        logger.exception('Chart render failed with matplotlib: %s: %s', type(exc).__name__, exc)
        return _svg_fallback()


def _build_chart_images(records):
    if not records:
        return {}

    charts = {}
    metric_defs = [
        ('heart_rate', [record.heart_rate for record in records], 'Heart Rate', '#1a73e8', 'bpm'),
        ('sleep', [record.sleep_hours for record in records], 'Sleep Hours', '#f5b041', 'hrs'),
        ('steps', [record.steps for record in records], 'Steps', '#1f9d63', 'steps'),
    ]

    for key, values, title, color, ylabel in metric_defs:
        try:
            image = _build_metric_chart(records, values, title, color, ylabel)
            if image:
                charts[key] = image
            else:
                logger.warning('Chart generation returned None for metric: %s', key)
        except Exception as exc:
            logger.exception('Chart generation failed for metric %s: %s: %s', key, type(exc).__name__, exc)

    if not charts:
        return {}
    return charts


def _build_insights(stats, total_days, high_hr_days, low_sleep_days):
    avg_heart_rate = stats.get('avg_heart_rate') or 0
    avg_sleep = stats.get('avg_sleep') or 0
    avg_steps = stats.get('avg_steps') or 0

    if high_hr_days > 0:
        hr_trend = f"Heart rate exceeded 110 bpm on {high_hr_days} day(s), suggesting periods of elevated stress or exertion."
    else:
        hr_trend = "No days exceeded 110 bpm, suggesting steady heart rate during this period."

    if low_sleep_days > 0:
        sleep_trend = f"Sleep fell below 5 hours on {low_sleep_days} day(s), which can reduce recovery when frequent."
    else:
        sleep_trend = "No nights dropped below 5 hours, indicating consistent sleep duration."

    activity_trend = f"Average daily steps were {avg_steps:.0f}, with {total_days} day(s) recorded overall."

    trends = [hr_trend, sleep_trend, activity_trend]

    recommendations = []
    if avg_sleep < 7 or low_sleep_days > 0:
        recommendations.append("Set a fixed bedtime and limit screens 30 minutes before sleep.")
    if high_hr_days > 0 or avg_heart_rate >= 95:
        recommendations.append("Add short breathing breaks or light recovery sessions on intense days.")
    if avg_steps < 7000:
        recommendations.append("Add a 10-minute walk after meals to lift daily steps.")
    recommendations.append("Hydrate steadily and keep caffeine earlier in the day.")
    recommendations = recommendations[:4]

    concerns = []
    if avg_heart_rate >= 100 or high_hr_days >= 3:
        concerns.append("Sustained elevated heart rate may indicate stress or strain.")
    if avg_sleep < 6 or low_sleep_days >= 3:
        concerns.append("Frequent short sleep can impact recovery and focus.")
    if avg_steps < 5000:
        concerns.append("Lower activity levels could be improved with light movement breaks.")
    if not concerns:
        concerns.append("No major concerns surfaced in the selected period.")

    next_steps = [
        "Review your top three highest heart rate days and note triggers.",
        "Set a 7-day sleep goal and track consistency.",
        "Revisit this report in two weeks to compare trends.",
    ]

    return {
        'trends': trends,
        'recommendations': recommendations,
        'concerns': concerns,
        'next_steps': next_steps,
    }


def get_report_data(request):
    today = date.today()
    start_param = _parse_date(request.GET.get('start'))
    end_param = _parse_date(request.GET.get('end'))

    if start_param and end_param:
        start_date, end_date = sorted([start_param, end_param])
    else:
        try:
            days = int(request.GET.get('days', 30))
        except (TypeError, ValueError):
            days = 30
        if days <= 0:
            days = 30
        if days > 365:
            days = 365
        end_date = today
        start_date = end_date - timedelta(days=days - 1)

    records = HealthRecord.objects.filter(
        user=request.user,
        date__range=(start_date, end_date),
    ).order_by('date')

    total_days = records.count()
    stats = records.aggregate(
        avg_heart_rate=Avg('heart_rate'),
        avg_sleep=Avg('sleep_hours'),
        avg_steps=Avg('steps'),
    )
    latest_record = records.order_by('-date').first()
    high_hr_days = records.filter(heart_rate__gt=110).count()
    low_sleep_days = records.filter(sleep_hours__lt=5.0).count()
    has_data = total_days > 0

    chart_records = list(records)
    if len(chart_records) > 30:
        chart_records = chart_records[-30:]

    chart_images = _build_chart_images(chart_records)

    last_7_start = max(start_date, end_date - timedelta(days=6))
    last_7_records = list(
        HealthRecord.objects.filter(
            user=request.user,
            date__range=(last_7_start, end_date),
        ).order_by('-date')
    )

    highlight_high_hr = records.order_by('-heart_rate', '-date').first() if has_data else None
    highlight_low_sleep = records.order_by('sleep_hours', '-date').first() if has_data else None
    alert_days = records.filter(Q(heart_rate__gt=110) | Q(sleep_hours__lt=5.0)).count()

    avg_heart_rate = stats.get('avg_heart_rate')
    if avg_heart_rate is None:
        hr_hint = '--'
    elif avg_heart_rate < 60:
        hr_hint = 'Below typical resting range.'
    elif avg_heart_rate <= 100:
        hr_hint = 'Within normal resting range.'
    else:
        hr_hint = 'Above typical resting range.'

    avg_sleep = stats.get('avg_sleep')
    if avg_sleep is None:
        sleep_hint = '--'
    elif avg_sleep < 6:
        sleep_hint = 'Below recommended 7-9 hours.'
    elif avg_sleep < 7:
        sleep_hint = 'Slightly below recommended 7-9 hours.'
    elif avg_sleep <= 9:
        sleep_hint = 'Within recommended 7-9 hours.'
    else:
        sleep_hint = 'Above typical sleep range.'

    avg_steps = stats.get('avg_steps')
    if avg_steps is None:
        steps_hint = '--'
    elif avg_steps < 5000:
        steps_hint = 'Below typical activity level.'
    elif avg_steps < 8000:
        steps_hint = 'Moderate activity level.'
    else:
        steps_hint = 'Good activity level.'

    exec_summary = []
    if has_data:
        exec_summary.append(
            f"Report covers {total_days} day(s) from {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}."
        )
        exec_summary.append(
            f"Average metrics: {avg_heart_rate:.0f} bpm heart rate, {avg_sleep:.1f} hours sleep, {avg_steps:.0f} steps."
        )
        if low_sleep_days >= high_hr_days and low_sleep_days > 0:
            exec_summary.append(
                f"Sleep dipped below 5 hours on {low_sleep_days} day(s), making recovery the primary watch area."
            )
        elif high_hr_days > 0:
            exec_summary.append(
                f"Heart rate exceeded 110 bpm on {high_hr_days} day(s), suggesting spikes worth monitoring."
            )
        else:
            exec_summary.append("No alert thresholds were triggered; overall stability looks good.")
    else:
        exec_summary = [
            "No records were available for this period.",
            "Add daily health entries to unlock insights and trends.",
        ]

    insights = _build_insights(stats, total_days, high_hr_days, low_sleep_days) if has_data else {
        'trends': ["No trends available for the selected period."],
        'recommendations': ["Add health records to generate tailored recommendations."],
        'concerns': ["No concerns available without recent data."],
        'next_steps': ["Log your daily health metrics to start tracking progress."],
    }

    return {
        'start_date': start_date,
        'end_date': end_date,
        'records': records,
        'total_days': total_days,
        'stats': stats,
        'latest_record': latest_record,
        'high_hr_days': high_hr_days,
        'low_sleep_days': low_sleep_days,
        'has_data': has_data,
        'chart_images': chart_images,
        'chart_records': chart_records,
        'last_7_records': last_7_records,
        'highlight_high_hr': highlight_high_hr,
        'highlight_low_sleep': highlight_low_sleep,
        'alert_days': alert_days,
        'kpi_hints': {
            'avg_heart_rate': hr_hint,
            'avg_sleep': sleep_hint,
            'avg_steps': steps_hint,
        },
        'exec_summary': exec_summary,
        'insights': insights,
    }


@login_required
def dashboard(request):
    """Main dashboard view showing health metrics and charts."""
    all_records = HealthRecord.objects.filter(user=request.user)
    if not all_records.exists():
        context = {
            'has_data': False,
            'message': 'No health data found. Please add records to get started.'
        }
        return render(request, 'health/dashboard.html', context)

    legacy_range = request.GET.get('range')
    hr_range = _parse_range_param(request.GET.get('hr_range') or legacy_range, {7, 30, 90}, 7)
    sleep_range = _parse_range_param(request.GET.get('sleep_range') or legacy_range, {7, 30, 90}, 7)
    kpi_range = _parse_range_param(request.GET.get('kpi_range') or legacy_range, {7, 30, 90}, 7)

    table_range_param = request.GET.get('table_range', str(kpi_range))
    table_range = 'all' if table_range_param == 'all' else _parse_range_param(table_range_param, {7, 30}, kpi_range)

    today = timezone.localdate()
    kpi_start = today - timedelta(days=kpi_range - 1)

    kpi_records = all_records.filter(date__gte=kpi_start, date__lte=today).order_by('date')

    if not kpi_records.exists():
        context = {
            'has_data': False,
            'message': 'No health data found in the selected range. Try a longer range.',
            'hr_range': hr_range,
            'sleep_range': sleep_range,
            'kpi_range': kpi_range,
            'table_range': table_range,
        }
        return render(request, 'health/dashboard.html', context)

    # Calculate statistics for KPI range
    stats = kpi_records.aggregate(
        avg_heart_rate=Avg('heart_rate'),
        avg_sleep=Avg('sleep_hours'),
        avg_steps=Avg('steps'),
        total_days=Count('id')
    )
    
    # Get latest record in KPI range for summary/alerts
    latest_record = kpi_records.last()
    alerts = check_latest_alerts(latest_record) if latest_record else {'has_alert': False, 'messages': []}
    
    hr_start = today - timedelta(days=hr_range - 1)
    sleep_start = today - timedelta(days=sleep_range - 1)

    hr_records = all_records.filter(date__gte=hr_start, date__lte=today).order_by('date')
    sleep_records = all_records.filter(date__gte=sleep_start, date__lte=today).order_by('date')

    hr_chart_data = _chart_payload(hr_records, 'heart_rate')
    sleep_chart_data = _chart_payload(sleep_records, 'sleep_hours')

    metric_fields = {
        'avg_heart_rate': 'heart_rate',
        'avg_sleep': 'sleep_hours',
        'avg_steps': 'steps',
    }

    def _trend_for(metric_field):
        current_avg = stats.get(metric_field)
        if current_avg is None:
            return {'label': 'N/A vs last period', 'css_class': 'kpi-trend-neutral', 'icon': 'fa-minus'}

        prev_end = kpi_start - timedelta(days=1)
        prev_start = prev_end - timedelta(days=kpi_range - 1)
        prev_avg = all_records.filter(date__gte=prev_start, date__lte=prev_end).aggregate(
            avg=Avg(metric_fields[metric_field])
        )['avg']

        if not prev_avg:
            return {'label': 'N/A vs last period', 'css_class': 'kpi-trend-neutral', 'icon': 'fa-minus'}

        percent = ((current_avg - prev_avg) / prev_avg) * 100
        if abs(percent) < 0.1:
            direction = 'kpi-trend-neutral'
            icon = 'fa-minus'
            label = '0.0% vs last period'
        else:
            direction = 'kpi-trend-up' if percent > 0 else 'kpi-trend-down'
            icon = 'fa-arrow-up' if percent > 0 else 'fa-arrow-down'
            label = f"{percent:+.1f}% vs last period"

        return {'label': label, 'css_class': direction, 'icon': icon}

    kpi_trends = {
        'heart_rate': _trend_for('avg_heart_rate'),
        'sleep': _trend_for('avg_sleep'),
        'steps': _trend_for('avg_steps'),
    }

    table_records = _get_table_records(all_records, table_range, today)
    table_links = _build_table_links(request, hr_range, sleep_range, kpi_range)

    context = {
        'has_data': True,
        'stats': stats,
        'latest_record': latest_record,
        'alerts': alerts,
        'hr_chart_data': hr_chart_data,
        'sleep_chart_data': sleep_chart_data,
        'total_records': all_records.count(),
        'recent_records': table_records,
        'hr_range': hr_range,
        'sleep_range': sleep_range,
        'kpi_range': kpi_range,
        'table_range': table_range,
        'table_link_7': table_links['7'],
        'table_link_30': table_links['30'],
        'table_link_all': table_links['all'],
        'kpi_trends': kpi_trends,
    }
    
    return render(request, 'health/dashboard.html', context)


@login_required
def dashboard_chart(request):
    chart_key = request.GET.get('chart')
    range_days = _parse_range_param(request.GET.get('range'), {7, 30, 90}, 7)
    today = timezone.localdate()
    start_date = today - timedelta(days=range_days - 1)
    records = HealthRecord.objects.filter(
        user=request.user,
        date__gte=start_date,
        date__lte=today,
    ).order_by('date')

    if chart_key == 'hr':
        payload = _chart_payload(records, 'heart_rate')
    elif chart_key == 'sleep':
        payload = _chart_payload(records, 'sleep_hours')
    else:
        return JsonResponse({'error': 'Invalid chart key.'}, status=400)

    return JsonResponse({'chart': chart_key, 'range': range_days, 'data': payload})


@login_required
def dashboard_records(request):
    all_records = HealthRecord.objects.filter(user=request.user)
    hr_range = _parse_range_param(request.GET.get('hr_range'), {7, 30, 90}, 7)
    sleep_range = _parse_range_param(request.GET.get('sleep_range'), {7, 30, 90}, 7)
    kpi_range = _parse_range_param(request.GET.get('kpi_range'), {7, 30, 90}, 7)

    table_range_param = request.GET.get('table_range', str(kpi_range))
    table_range = 'all' if table_range_param == 'all' else _parse_range_param(table_range_param, {7, 30}, kpi_range)
    today = timezone.localdate()

    table_records = _get_table_records(all_records, table_range, today)
    table_links = _build_table_links(request, hr_range, sleep_range, kpi_range)

    context = {
        'recent_records': table_records,
        'table_range': table_range,
        'hr_range': hr_range,
        'sleep_range': sleep_range,
        'kpi_range': kpi_range,
        'table_link_7': table_links['7'],
        'table_link_30': table_links['30'],
        'table_link_all': table_links['all'],
    }
    html = render_to_string('health/partials/recent_records.html', context, request=request)
    return HttpResponse(html)


@login_required
def health_report_pdf(request):
    try:
        from weasyprint import HTML
    except Exception:
        return HttpResponse(
            'PDF reports are unavailable because WeasyPrint is not installed on this server.',
            content_type='text/plain',
            status=500,
        )

    report_data = get_report_data(request)
    user_display = request.user.get_full_name().strip() or request.user.get_username()
    date_range = f"{report_data['start_date'].strftime('%b %d, %Y')} - {report_data['end_date'].strftime('%b %d, %Y')}"

    generated_on_display = timezone.localtime().strftime('%b %d, %Y %H:%M')
    context = {
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

    if report_data['has_data'] and not report_data['chart_images']:
        logger.warning('Chart generation returned None for report despite available data.')

    html = render_to_string('reports/health_report.html', context)
    base_url = request.build_absolute_uri('/')

    try:
        pdf = HTML(string=html, base_url=base_url).write_pdf()
    except Exception:
        return HttpResponse(
            'We could not generate the PDF report right now. Please try again later.',
            content_type='text/plain',
            status=500,
        )

    safe_username = slugify(request.user.get_username()) or 'user'
    filename_date = report_data['end_date'].strftime('%Y%m%d')
    filename = f'health_report_{safe_username}_{filename_date}.pdf'

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
def log_data(request):
    """View for adding and managing health records."""
    form = HealthRecordForm()
    if request.method == 'POST':
        form = HealthRecordForm(request.POST)
        if form.is_valid():
            record_date = form.cleaned_data['date']
            existing = HealthRecord.objects.filter(user=request.user, date=record_date).first()
            if existing:
                for field, value in form.cleaned_data.items():
                    setattr(existing, field, value)
                existing.save()
                messages.success(request, f'Record for {record_date} updated successfully!')
            else:
                record = form.save(commit=False)
                record.user = request.user
                record.save()
                messages.success(request, f'Record for {record_date} added successfully!')
            return redirect(f"{reverse('health:log_data')}?saved={record_date}")
    
    # Get all records
    records = HealthRecord.objects.filter(user=request.user).order_by('-date')
    
    context = {
        'records': records,
        'today': date.today(),
        'form': form,
    }
    
    return render(request, 'health/log_data.html', context)


@login_required
def edit_record(request, record_id):
    """View for editing a specific health record."""
    record = get_object_or_404(HealthRecord, id=record_id, user=request.user)
    
    form = HealthRecordForm(instance=record)
    if request.method == 'POST':
        form = HealthRecordForm(request.POST, instance=record)
        if form.is_valid():
            updated_record = form.save(commit=False)
            updated_record.user = request.user
            updated_record.save()
            messages.success(request, 'Record updated successfully!')
            return redirect('health:log_data')
    
    context = {
        'record': record,
        'form': form,
    }
    
    return render(request, 'health/edit_record.html', context)


@login_required
def delete_record(request, record_id):
    """View for deleting a health record."""
    record = get_object_or_404(HealthRecord, id=record_id, user=request.user)
    
    if request.method == 'POST':
        record.delete()
        messages.success(request, 'Record deleted successfully!')
        return redirect('health:log_data')
    
    context = {
        'record': record,
    }
    
    return render(request, 'health/delete_record.html', context)


def build_ai_summary(records):
    df = pd.DataFrame(list(records.values('date', 'heart_rate', 'sleep_hours', 'steps')))
    df['date'] = pd.to_datetime(df['date'])
    avg_heart_rate = df['heart_rate'].mean()
    avg_sleep = df['sleep_hours'].mean()
    avg_steps = df['steps'].mean()
    high_hr_days = len(df[df['heart_rate'] > 110])
    low_sleep_days = len(df[df['sleep_hours'] < 5.0])
    latest = df.iloc[-1]

    return f"""
Health Data Summary (Last {len(df)} days):

Average Metrics:
- Heart Rate: {avg_heart_rate:.1f} bpm
- Sleep: {avg_sleep:.1f} hours per night
- Steps: {avg_steps:.0f} steps per day

Alert Days:
- High Heart Rate (>110 bpm): {high_hr_days} days
- Low Sleep (<5 hours): {low_sleep_days} days

Latest Record ({latest['date'].strftime('%Y-%m-%d')}):
- Heart Rate: {int(latest['heart_rate'])} bpm
- Sleep: {latest['sleep_hours']:.1f} hours
- Steps: {int(latest['steps'])} steps
"""


@login_required
@require_POST
def ai_doctor_insights_api(request):
    records = HealthRecord.objects.filter(user=request.user).order_by('date')
    if not records.exists():
        return JsonResponse(
            {
                'success': False,
                'error': 'No health data found. Please add records to get AI insights.',
                'error_type': 'no_data',
            },
            status=400,
        )

    ai_available = get_ai_client() is not None
    if not ai_available:
        return JsonResponse(
            {
                'success': False,
                'error': 'AI is not configured on this server.',
                'error_type': 'missing_api_key',
            },
            status=400,
        )

    custom_prompt = request.POST.get('custom_prompt', '')
    summary = build_ai_summary(records)

    try:
        result = get_ai_insights(
            prompt=custom_prompt if custom_prompt else None,
            summary_override=summary,
        )
        if result.get('success'):
            ai_response = result.get('response')
            if not ai_response:
                return JsonResponse(
                    {
                        'success': False,
                        'error': 'No insights were returned. Please try again.',
                        'error_type': 'empty_response',
                    },
                    status=502,
                )
            return JsonResponse({'success': True, 'response': ai_response})

        error_type = result.get('error_type')
        if error_type == 'missing_api_key':
            ai_error = 'AI is not configured on this server.'
        elif error_type == 'rate_limited':
            ai_error = 'AI is busy, try again in a minute.'
        elif error_type == 'timeout':
            ai_error = 'Request timed out, try again.'
        else:
            ai_error = result.get('error') or 'AI service did not return a response.'
        return JsonResponse(
            {
                'success': False,
                'error': ai_error,
                'error_type': error_type or 'ai_error',
            },
            status=502,
        )
    except Exception as exc:
        print(f'AI insight generation failed: {exc}')
        return JsonResponse(
            {
                'success': False,
                'error': 'We could not generate insights right now. Please try again.',
                'error_type': 'exception',
            },
            status=500,
        )


@login_required
def ai_doctor(request):
    """View for AI-powered health insights."""
    records = HealthRecord.objects.filter(user=request.user).order_by('date')
    
    if not records.exists():
        context = {
            'has_data': False,
            'message': 'No health data found. Please add records to get AI insights.'
        }
        return render(request, 'health/ai_doctor.html', context)
    
    # Calculate statistics
    stats = records.aggregate(
        avg_heart_rate=Avg('heart_rate'),
        avg_sleep=Avg('sleep_hours'),
        avg_steps=Avg('steps'),
        total_days=Count('id')
    )
    
    # Get latest record for alerts
    latest_record = records.first()
    alerts = check_latest_alerts(latest_record) if latest_record else {'has_alert': False, 'messages': []}
    
    # AI insights
    ai_response = None
    ai_error = None
    insight_requested = request.method == 'POST' and 'get_insights' in request.POST
    ai_available = get_ai_client() is not None
    
    if insight_requested:
        try:
            if not ai_available:
                ai_error = 'AI is not configured on this server.'
                messages.error(request, ai_error)
            else:
                custom_prompt = request.POST.get('custom_prompt', '')
                summary = build_ai_summary(records)

                result = get_ai_insights(
                    prompt=custom_prompt if custom_prompt else None,
                    summary_override=summary
                )
                
                if result.get('success'):
                    ai_response = result.get('response')
                    if not ai_response:
                        ai_error = 'No insights were returned. Please try again.'
                        messages.error(request, ai_error)
                else:
                    error_type = result.get('error_type')
                    if error_type == 'missing_api_key':
                        ai_error = 'AI is not configured on this server.'
                    elif error_type == 'rate_limited':
                        ai_error = 'AI is busy, try again in a minute.'
                    elif error_type == 'timeout':
                        ai_error = 'Request timed out, try again.'
                    else:
                        ai_error = result.get('error') or 'AI service did not return a response.'
                    messages.error(request, ai_error)
        except Exception as exc:
            ai_error = 'We could not generate insights right now. Please try again.'
            messages.error(request, ai_error)
            print(f'AI insight generation failed: {exc}')
    
    context = {
        'has_data': True,
        'stats': stats,
        'latest_record': latest_record,
        'alerts': alerts,
        'ai_response': ai_response,
        'ai_error': ai_error,
        'ai_available': ai_available,
        'insight_requested': insight_requested,
    }
    
    return render(request, 'health/ai_doctor.html', context)


@login_required
def settings_view(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        if 'save_profile' in request.POST:
            user_form = UserSettingsForm(request.POST, instance=request.user)
            profile_form = ProfileForm(request.POST, request.FILES, instance=profile)
            password_form = PasswordChangeForm(request.user)
            if user_form.is_valid() and profile_form.is_valid():
                user_form.save()
                profile_form.save()
                messages.success(request, 'Profile updated successfully.')
                return redirect('health:settings')
        elif 'change_password' in request.POST:
            user_form = UserSettingsForm(instance=request.user)
            profile_form = ProfileForm(instance=profile)
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Password updated successfully.')
                return redirect('health:settings')
    else:
        user_form = UserSettingsForm(instance=request.user)
        profile_form = ProfileForm(instance=profile)
        password_form = PasswordChangeForm(request.user)

    for field in password_form.fields.values():
        field.widget.attrs.setdefault('class', 'form-control')

    context = {
        'user_form': user_form,
        'profile_form': profile_form,
        'password_form': password_form,
    }
    return render(request, 'health/settings.html', context)


class DemoPasswordResetView(PasswordResetView):
    template_name = 'registration/password_reset_form.html'
    success_url = reverse_lazy('health:password_reset_done')

    def post(self, request, *args, **kwargs):
        cooldown_seconds = 60
        last_requested = request.session.get('password_reset_last')
        if last_requested:
            try:
                last_dt = datetime.fromisoformat(last_requested)
                elapsed = (timezone.now() - last_dt).total_seconds()
                if elapsed < cooldown_seconds:
                    form = self.get_form()
                    form.add_error(None, 'Please wait a moment before requesting another reset link.')
                    return self.form_invalid(form)
            except ValueError:
                pass
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        request = self.request
        request.session['password_reset_last'] = timezone.now().isoformat()
        debug_link = None

        for user in form.get_users(form.cleaned_data["email"]):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            debug_link = request.build_absolute_uri(
                reverse('health:password_reset_confirm', args=[uid, token])
            )
            break

        request.session['debug_reset_link'] = debug_link
        return redirect(self.get_success_url())


class DemoPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'registration/password_reset_done.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['debug_reset_link'] = self.request.session.pop('debug_reset_link', None)
        context['debug_mode'] = settings.DEBUG
        return context
