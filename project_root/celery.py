import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_root.settings')
app = Celery('project_root')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


app.conf.beat_schedule = {
    'fetch-every-2-minutes': {
        'task': 'calendy.tasks.fetch_new_appointments_task',
        'schedule': crontab(minute='*/2'), 
    },
    'notifiation-send-scheduled-emails': {
        'task': 'notifiation.tasks.send_scheduled_emails_task',
        'schedule': crontab(minute='*/1'),
    },
}