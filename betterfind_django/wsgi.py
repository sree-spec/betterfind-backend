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
    from django.core.management import call_command
    print("🚀 Running migrations on startup...")
    call_command('migrate', interactive=False)
    print("✅ Migrations completed successfully!")
except Exception as e:
    print(f"❌ Error running migrations on startup: {e}")

