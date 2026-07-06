from django.core.management.base import BaseCommand
from notifiation.tasks import send_scheduled_emails_task
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Test the email scheduler task immediately'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('Running email scheduler task...'))
        
        # Configure logging to see output
        logging.basicConfig(level=logging.INFO)
        
        try:
            count = send_scheduled_emails_task()
            self.stdout.write(
                self.style.SUCCESS(f'✓ Task completed. Sent {count} emails.')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'✗ Task failed: {str(e)}')
            )
