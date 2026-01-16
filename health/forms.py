from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import HealthRecord, Profile


class HealthRecordForm(forms.ModelForm):
    class Meta:
        model = HealthRecord
        fields = ['date', 'heart_rate', 'sleep_hours', 'steps']

    def clean_sleep_hours(self):
        sleep_hours = self.cleaned_data.get('sleep_hours')
        if sleep_hours is not None:
            if sleep_hours < 0 or sleep_hours > 24:
                raise forms.ValidationError('Sleep hours must be between 0 and 24.')
        return sleep_hours

    def clean_heart_rate(self):
        heart_rate = self.cleaned_data.get('heart_rate')
        if heart_rate is not None:
            if heart_rate < 30 or heart_rate > 220:
                raise forms.ValidationError('Heart rate must be between 30 and 220 bpm.')
        return heart_rate

    def clean_steps(self):
        steps = self.cleaned_data.get('steps')
        if steps is not None and steps < 0:
            raise forms.ValidationError('Steps must be 0 or more.')
        return steps


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']


class UserSettingsForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].disabled = True
        self.fields['email'].required = False
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['avatar'].widget.attrs.setdefault('class', 'form-control')


class ReportScheduleForm(forms.ModelForm):
    RANGE_CHOICES = (
        (7, 'Last 7 days'),
        (30, 'Last 30 days'),
        (90, 'Last 90 days'),
    )

    report_range_days = forms.ChoiceField(choices=RANGE_CHOICES)

    class Meta:
        model = Profile
        fields = [
            'report_schedule_enabled',
            'report_recipient_email',
            'report_frequency',
            'report_day_of_week',
            'report_day_of_month',
            'report_time',
            'report_range_days',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['report_schedule_enabled'].widget.attrs.setdefault('class', 'form-check-input')
        self.fields['report_recipient_email'].widget.attrs.setdefault('class', 'form-control')
        self.fields['report_frequency'].widget.attrs.setdefault('class', 'form-select')
        self.fields['report_day_of_week'].widget.attrs.setdefault('class', 'form-select')
        self.fields['report_day_of_month'].widget.attrs.setdefault('class', 'form-control')
        self.fields['report_time'].widget.attrs.setdefault('class', 'form-control')
        self.fields['report_range_days'].widget.attrs.setdefault('class', 'form-select')
        self.fields['report_time'].widget.input_type = 'time'
        self.fields['report_day_of_month'].widget.attrs.setdefault('min', 1)
        self.fields['report_day_of_month'].widget.attrs.setdefault('max', 28)

    def clean(self):
        cleaned = super().clean()
        enabled = cleaned.get('report_schedule_enabled')
        frequency = cleaned.get('report_frequency')
        day_of_week = cleaned.get('report_day_of_week')
        day_of_month = cleaned.get('report_day_of_month')
        report_time = cleaned.get('report_time')
        recipient = cleaned.get('report_recipient_email')
        range_days = cleaned.get('report_range_days')

        if not enabled:
            cleaned['report_day_of_week'] = None
            cleaned['report_day_of_month'] = None
            return cleaned

        if not recipient:
            fallback = getattr(self.instance.user, 'email', None)
            if fallback:
                cleaned['report_recipient_email'] = fallback
            else:
                self.add_error('report_recipient_email', 'Add an email address to receive the report.')

        if not report_time:
            self.add_error('report_time', 'Choose a send time.')

        try:
            range_value = int(range_days) if range_days is not None else None
        except (TypeError, ValueError):
            range_value = None
        if range_value not in {7, 30, 90}:
            self.add_error('report_range_days', 'Pick a valid report range (7/30/90 days).')
        else:
            cleaned['report_range_days'] = range_value

        if frequency == 'weekly':
            cleaned['report_day_of_month'] = None
            if not day_of_week:
                self.add_error('report_day_of_week', 'Select which day to send the weekly report.')
        elif frequency == 'monthly':
            cleaned['report_day_of_week'] = None
            if day_of_month is None:
                self.add_error('report_day_of_month', 'Pick the day of the month to send the report.')
            else:
                if day_of_month < 1 or day_of_month > 28:
                    self.add_error('report_day_of_month', 'Choose a day between 1 and 28 for reliability.')
        else:
            cleaned['report_day_of_week'] = None
            cleaned['report_day_of_month'] = None

        return cleaned
