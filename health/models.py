from datetime import datetime, timedelta, time as dt_time
from calendar import monthrange
from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class HealthRecord(models.Model):
    """
    Health record model representing a single day's health data.
    """
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='health_records',
        null=True,
        blank=True,
    )
    date = models.DateField(db_index=True)
    heart_rate = models.IntegerField(
        validators=[MinValueValidator(40), MaxValueValidator(200)],
        help_text="Heart rate in beats per minute"
    )
    sleep_hours = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(24.0)],
        help_text="Hours of sleep"
    )
    steps = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Number of steps taken"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Health Record'
        verbose_name_plural = 'Health Records'
        unique_together = ('user', 'date')

    def __str__(self):
        return f"Health Record - {self.date}"

    def has_alerts(self):
        """Check if this record has any health alerts."""
        alerts = []
        if self.heart_rate > 110:
            alerts.append('high_heart_rate')
        if self.sleep_hours < 5.0:
            alerts.append('low_sleep')
        return alerts

    def to_dict(self):
        """Convert record to dictionary for serialization."""
        return {
            'id': self.id,
            'date': self.date.isoformat(),
            'heart_rate': self.heart_rate,
            'sleep_hours': self.sleep_hours,
            'steps': self.steps,
        }


class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    report_schedule_enabled = models.BooleanField(default=False)
    report_frequency = models.CharField(
        max_length=10,
        choices=[
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        default='daily',
    )
    report_time = models.TimeField(null=True, blank=True, default=dt_time(hour=8, minute=0))
    report_day_of_week = models.CharField(
        max_length=9,
        choices=[
            ('monday', 'Monday'),
            ('tuesday', 'Tuesday'),
            ('wednesday', 'Wednesday'),
            ('thursday', 'Thursday'),
            ('friday', 'Friday'),
            ('saturday', 'Saturday'),
            ('sunday', 'Sunday'),
        ],
        null=True,
        blank=True,
    )
    report_day_of_month = models.PositiveSmallIntegerField(null=True, blank=True)
    report_recipient_email = models.EmailField(null=True, blank=True)
    report_range_days = models.PositiveSmallIntegerField(default=30)
    next_report_at = models.DateTimeField(null=True, blank=True)
    last_report_sent_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.username}"

    def compute_next_report_at(self, now=None):
        """
        Compute and set the next datetime a report should be sent.
        """
        if not self.report_schedule_enabled or not self.report_time:
            self.next_report_at = None
            return None

        now = now or timezone.localtime()
        tz = timezone.get_current_timezone()
        today = now.date()

        def _make_dt(target_date):
            dt = datetime.combine(target_date, self.report_time)
            return timezone.make_aware(dt, tz) if timezone.is_naive(dt) else dt

        if self.report_frequency == 'daily':
            candidate = _make_dt(today)
            if candidate <= now:
                candidate = _make_dt(today + timedelta(days=1))
        elif self.report_frequency == 'weekly':
            weekday_index = {
                'monday': 0,
                'tuesday': 1,
                'wednesday': 2,
                'thursday': 3,
                'friday': 4,
                'saturday': 5,
                'sunday': 6,
            }
            target_idx = weekday_index.get(self.report_day_of_week, today.weekday())
            days_ahead = (target_idx - today.weekday()) % 7
            candidate_date = today + timedelta(days=days_ahead)
            candidate = _make_dt(candidate_date)
            if candidate <= now:
                candidate = _make_dt(candidate_date + timedelta(days=7))
        else:  # monthly
            day_of_month = self.report_day_of_month or today.day

            def _month_candidate(year, month):
                last_day = monthrange(year, month)[1]
                safe_day = min(day_of_month, last_day)
                return _make_dt(datetime(year, month, safe_day).date())

            candidate = _month_candidate(today.year, today.month)
            if candidate <= now:
                year = today.year + (1 if today.month == 12 else 0)
                month = 1 if today.month == 12 else today.month + 1
                candidate = _month_candidate(year, month)

        self.next_report_at = candidate
        return candidate


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
