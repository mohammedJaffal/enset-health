from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Avg, Count
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse, reverse_lazy
from django.views.decorators.http import require_POST
from datetime import date, timedelta, datetime
from .models import HealthRecord, Profile
from .forms import HealthRecordForm, RegistrationForm, UserSettingsForm, ProfileForm
from services.ai_service import get_ai_insights, get_ai_client
from services.utils import check_latest_alerts
import pandas as pd


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


@login_required
def dashboard(request):
    """Main dashboard view showing health metrics and charts."""
    records = HealthRecord.objects.filter(user=request.user).order_by('date')
    
    if not records.exists():
        context = {
            'has_data': False,
            'message': 'No health data found. Please add records to get started.'
        }
        return render(request, 'health/dashboard.html', context)
    
    # Calculate statistics
    stats = records.aggregate(
        avg_heart_rate=Avg('heart_rate'),
        avg_sleep=Avg('sleep_hours'),
        avg_steps=Avg('steps'),
        total_days=Count('id')
    )
    
    # Get latest record for alerts
    latest_record = records.last()
    alerts = check_latest_alerts(latest_record) if latest_record else {'has_alert': False, 'messages': []}
    
    # Prepare data for charts
    df = pd.DataFrame(list(records.values('date', 'heart_rate', 'sleep_hours', 'steps')))
    df['date'] = pd.to_datetime(df['date'])
    
    # Chart data
    chart_data = {
        'dates': df['date'].dt.strftime('%Y-%m-%d').tolist(),
        'heart_rates': df['heart_rate'].tolist(),
        'sleep_hours': df['sleep_hours'].tolist(),
        'steps': df['steps'].tolist(),
    }
    
    context = {
        'has_data': True,
        'stats': stats,
        'latest_record': latest_record,
        'alerts': alerts,
        'chart_data': chart_data,
        'total_records': records.count(),
        'recent_records': records.order_by('-date')[:5],
    }
    
    return render(request, 'health/dashboard.html', context)


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
