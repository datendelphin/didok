import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'didok.settings'

sys.path.append('/home/spreng/git/didok/django/src')
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()

