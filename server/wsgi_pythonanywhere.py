"""
WSGI Configuration for PythonAnywhere (ssamu.pythonanywhere.com) & Local Testing.

Mounts:
- Django WSGI at root ('/admin/', '/api/', and redirects '/' to '/dashboard/')
- Dash Web Application at '/dashboard/' via Werkzeug DispatcherMiddleware
"""
import os
import sys

# Add server directory to sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Support PythonAnywhere virtualenv paths if deployed to /home/ssamu/
pa_home = '/home/ssamu'
if os.path.isdir(pa_home):
    if pa_home not in sys.path:
        sys.path.insert(0, pa_home)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'API.settings')

import django
django.setup()

from django.core.wsgi import get_wsgi_application
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from dashboard.app import app as dash_app

# Django WSGI application (handles /admin/, /api/, and redirects / to /dashboard/)
django_app = get_wsgi_application()

# DispatcherMiddleware:
# - Requests under '/dashboard' are routed directly to the Dash/Flask WSGI server.
# - All other requests (such as '/admin/', '/api/', and '/') are handled by Django.
application = DispatcherMiddleware(
    django_app,
    {
        '/dashboard': dash_app.server,
    }
)

if __name__ == '__main__':
    from werkzeug.serving import run_simple
    print("Iniciando servidor unificado Django + Dash en http://127.0.0.1:8000/ ...")
    print(" -> Dashboard: http://127.0.0.1:8000/dashboard/")
    print(" -> Django API: http://127.0.0.1:8000/api/datos/")
    print(" -> Django Admin: http://127.0.0.1:8000/admin/")
    run_simple('127.0.0.1', 8000, application, use_reloader=True, use_debugger=True)
