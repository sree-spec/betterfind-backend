"""
WSGI config for betterfind_django project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betterfind_django.settings')

application = get_wsgi_application()

# Run migrations automatically on startup
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [row[0] for row in cursor.fetchall()]
        if tables:
            print(f"🔥 Resetting database tables: {tables}")
            for table in tables:
                cursor.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
            print("✅ Database reset complete.")

    from django.core.management import call_command
    print("🚀 Running migrations on startup...")
    call_command('migrate', interactive=False)
    print("✅ Migrations completed successfully!")
except Exception as e:
    print(f"❌ Error running migrations on startup: {e}")

