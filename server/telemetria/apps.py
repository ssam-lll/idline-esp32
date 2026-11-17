from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _configure_sqlite(sender, connection, **kwargs):
    """Configure SQLite busy_timeout and temp_store (avoid WAL on NFS filesystems like PythonAnywhere)."""
    if connection.vendor == 'sqlite':
        with connection.cursor() as cursor:
            cursor.execute('PRAGMA temp_store=MEMORY;')
            cursor.execute('PRAGMA busy_timeout=5000;')


class TelemetriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'telemetria'
    verbose_name = 'Telemetría Robot IDLine'

    def ready(self):
        connection_created.connect(_configure_sqlite, dispatch_uid='telemetria_sqlite_wal')
