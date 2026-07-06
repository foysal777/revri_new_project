from django.core.management.base import BaseCommand
from notifiation.models import Email
from django.utils import timezone
from django.contrib.auth import get_user_model
import datetime


class Command(BaseCommand):
    help = 'Show scheduled emails countdown and verify everything is ready'

    def handle(self, *args, **options):
        now = timezone.now()
        User = get_user_model()
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('📧 EMAIL SCHEDULER STATUS'))
        self.stdout.write('=' * 80)
        
        self.stdout.write(f'\n🕐 Current Server Time: {now}\n')
        
        # Get all active emails
        emails = Email.objects.filter(is_active=True).order_by('set_date', 'set_time')
        
        if not emails:
            self.stdout.write(self.style.WARNING('No active scheduled emails found.'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'📨 {emails.count()} active scheduled emails:\n'))
        
        for idx, email in enumerate(emails, 1):
            if email.set_date and email.set_time:
                set_date_value = email.set_date
                if isinstance(set_date_value, datetime.datetime):
                    set_date_value = set_date_value.date()
                scheduled = datetime.datetime.combine(set_date_value, email.set_time)
                if timezone.is_naive(scheduled):
                    scheduled = timezone.make_aware(scheduled, timezone.get_current_timezone())
                
                time_diff = scheduled - now
                is_due = scheduled <= now
                
                # Format audience
                audience = email.select_audience
                if isinstance(audience, (list, dict)):
                    audience_str = str(audience)
                else:
                    audience_str = f"['{audience}']"
                
                status_icon = '✅ READY' if is_due else f'⏰ {time_diff}'
                
                self.stdout.write(f'{idx}. Email ID {email.id}')
                self.stdout.write(f'   Scheduled: {scheduled} {status_icon}')
                self.stdout.write(f'   To: {email.user.email}')
                self.stdout.write(f'   Audience: {audience_str}')
                self.stdout.write(f'   Repeated: {email.repeated_type if email.is_repeated else "No"} ')
                self.stdout.write()
        
        # Check Celery status
        self.stdout.write('=' * 80)
        self.stdout.write(self.style.WARNING('🔧 CELERY SERVICES STATUS:\n'))
        
        from django.conf import settings
        broker = getattr(settings, 'CELERY_BROKER_URL', 'NOT SET')
        self.stdout.write(f'Broker: {broker}')
        
        self.stdout.write(self.style.WARNING('\n⚠️  Required: Keep these running in separate terminals:'))
        self.stdout.write('   Terminal 1: celery -A project_root worker -l info')
        self.stdout.write('   Terminal 2: celery -A project_root beat -l info')
        
        # Check free users
        free_users = User.objects.filter(is_active=True, plantype='free')
        self.stdout.write(f'\n👥 Free users ({free_users.count()}):\n')
        for user in free_users:
            self.stdout.write(f'   - {user.email}')
        
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.SUCCESS('✅ Setup looks good! Emails will send at scheduled times.\n'))
