from django.core.management.base import BaseCommand
from notifiation.models import Email
from django.utils import timezone
from datetime import datetime, time


class Command(BaseCommand):
    help = 'Fix/validate email records and show status'

    def add_arguments(self, parser):
        parser.add_argument('--fix-missing-dates', action='store_true',
                            help='Set missing set_date to today for emails with missing dates')

    def handle(self, *args, **options):
        now = timezone.now()
        emails = Email.objects.filter(is_active=True)
        
        self.stdout.write(f'\n📧 Email Scheduler Status Report\n')
        self.stdout.write(f'Current time: {now}\n')
        self.stdout.write('=' * 70)
        
        for email in emails:
            self.stdout.write(f'\nEmail ID: {email.id}')
            self.stdout.write(f'  User: {email.user.email}')
            self.stdout.write(f'  Date: {email.set_date} | Time: {email.set_time}')
            self.stdout.write(f'  Audience: {email.select_audience}')
            self.stdout.write(f'  Repeated: {email.is_repeated} ({email.repeated_type})')
            
            # Validate
            issues = []
            if not email.set_date:
                issues.append('❌ Missing set_date')
            if not email.set_time:
                issues.append('❌ Missing set_time')
            if not email.select_audience:
                issues.append('❌ Empty select_audience')
            
            if email.set_date and email.set_time:
                import datetime as dt
                set_date_value = email.set_date
                if isinstance(set_date_value, dt.datetime):
                    set_date_value = set_date_value.date()
                scheduled = dt.datetime.combine(set_date_value, email.set_time)
                if timezone.is_naive(scheduled):
                    scheduled = timezone.make_aware(scheduled, timezone.get_current_timezone())
                
                if scheduled <= now:
                    self.stdout.write(f'  ✓ Due now! (scheduled: {scheduled})')
                else:
                    self.stdout.write(f'  ⏰ Not yet due (scheduled: {scheduled}, in {scheduled - now})')
            
            if issues:
                for issue in issues:
                    self.stdout.write(f'  {issue}')
        
        self.stdout.write('\n' + '=' * 70)
        
        # Optionally fix missing dates
        if options['fix_missing_dates']:
            today = now.date()
            fixed = Email.objects.filter(is_active=True, set_date__isnull=True).update(
                set_date=today
            )
            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Fixed {fixed} emails with missing dates (set to today)')
            )
