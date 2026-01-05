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
