import os
from pathlib import Path
from celery import Celery
from decouple import Config, RepositoryEnv

BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
if env_path.exists():
    os.environ.update(RepositoryEnv(str(env_path)).data)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tmsgroups.settings')

app = Celery('tmsgroups')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()