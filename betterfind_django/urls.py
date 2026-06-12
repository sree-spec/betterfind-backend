from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.views.static import serve
from django.views.generic import RedirectView
import os

# Calculate the path to the dashboard folder
DASHBOARD_DIR = os.path.join(settings.BASE_DIR.parent.parent, 'dashboard')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('api/', include('telemetry.urls')),
    
    # Redirect the blank root URL to the login page
    path('', RedirectView.as_view(url='/login.html', permanent=False)),
    
    # Catch-all to serve HTML, CSS, JS, and image files directly from the dashboard folder
    re_path(r'^(?P<path>.*)$', serve, {'document_root': DASHBOARD_DIR}),
]
