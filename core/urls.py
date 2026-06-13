from django.urls import path
from .views import RegisterView, CustomLoginView, InviteGuardianView, ListGuardiansView, HealthView

urlpatterns = [
    path('auth/register', RegisterView.as_view(), name='register'),
    path('auth/login', CustomLoginView.as_view(), name='login'),
    path('guardians/', ListGuardiansView.as_view(), name='list-guardians'),
    path('guardians/invite/', InviteGuardianView.as_view(), name='invite-guardian'),
    path('health/', HealthView.as_view(), name='health'),

]
