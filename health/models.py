from django.conf import settings
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator


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
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Profile: {self.user.username}"


@receiver(post_save, sender=get_user_model())
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
