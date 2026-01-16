import logging
import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from health.models import Profile
from health.reporting import send_report_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send scheduled health report emails for users who are due."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='List which reports would be sent without sending emails.',
        )
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Run continuously, checking on an interval instead of exiting after one pass.',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=300,
            help='Seconds to sleep between checks when using --loop (default: 300).',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        loop = options.get('loop')
        interval = max(30, options.get('interval') or 300)

        def _run_once():
            now = timezone.localtime()
            profiles = Profile.objects.select_related('user').filter(report_schedule_enabled=True)
            sent = 0
            skipped = 0

            for profile in profiles:
                next_at = profile.next_report_at
                if not next_at or next_at > now:
                    skipped += 1
                    continue

                recipient = profile.report_recipient_email or profile.user.email
                if not recipient:
                    logger.warning('Skipping user %s: no recipient email configured.', profile.user_id)
                    skipped += 1
                    continue

                if dry_run:
                    self.stdout.write(f"[DRY RUN] Would send report to {recipient} for user {profile.user_id}")
                    continue

                try:
                    send_report_email(profile.user, recipient, range_days=profile.report_range_days)
                    profile.last_report_sent_at = now
                    profile.compute_next_report_at(now=now)
                    profile.save(
                        update_fields=[
                            'last_report_sent_at',
                            'next_report_at',
                            'report_schedule_enabled',
                            'report_frequency',
                            'report_day_of_week',
                            'report_day_of_month',
                            'report_time',
                            'report_range_days',
                            'report_recipient_email',
                            'updated_at',
                        ]
                    )
                    sent += 1
                except Exception as exc:  # pragma: no cover - network failures
                    logger.exception('Failed to send scheduled report for user %s: %s', profile.user_id, exc)
                    skipped += 1

            self.stdout.write(self.style.SUCCESS(f"Sent {sent} report(s); skipped {skipped} not due."))

        _run_once()
        if loop:
            self.stdout.write(self.style.WARNING(f"--loop enabled; sleeping {interval}s between checks. Ctrl+C to stop."))
            try:
                while True:
                    time.sleep(interval)
                    _run_once()
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Stopped send_scheduled_reports loop."))
