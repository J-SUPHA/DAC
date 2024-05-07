from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'NousDA.settings')

app = Celery('NousDA')

app.conf.task_time_limit = 400  # hard time limit in seconds

app.conf.task_soft_time_limit = 320  # soft time limit in seconds

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - Load configuration from Django settings, the CELERY namespace means all celery-related setting keys should have `CELERY_` as a prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

app.conf.beat_schedule = {
    'run_my_sceduled_task_every_60_seconds': {
        'task': 'catalog.tasks.my_scheduled_task',
        'schedule': 60.0,
    }
}