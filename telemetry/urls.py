from django.urls import path
from .views import LinkDeviceView, TrackDataView, LatestDataView, DeviceListView, DeviceHistoryView, GeoFenceListCreateView, GeoFenceDetailView, KnownWiFiEnvironmentListCreateView, KnownWiFiEnvironmentDetailView, GeoFenceLogListView, SmsWebhookView, AdminStatsView

urlpatterns = [
    path('admin/stats/', AdminStatsView.as_view(), name='admin-stats'),
    path('device/link/', LinkDeviceView.as_view(), name='device-link'),
    path('devices/', DeviceListView.as_view(), name='device-list'),
    path('track/', TrackDataView.as_view(), name='track-data'),
    path('device/<str:device_id>/latest/', LatestDataView.as_view(), name='latest-data'),
    path('device/<str:device_id>/history/<str:data_type>/', DeviceHistoryView.as_view(), name='device-history'),
    path('device/<str:device_id>/geofences/', GeoFenceListCreateView.as_view(), name='device-geofences'),
    path('device/<str:device_id>/geofences/<uuid:fence_id>/', GeoFenceDetailView.as_view(), name='device-geofence-detail'),
    path('device/<str:device_id>/wifi-environments/', KnownWiFiEnvironmentListCreateView.as_view(), name='wifi-environments-list'),
    path('device/<str:device_id>/wifi-environments/<uuid:env_id>/', KnownWiFiEnvironmentDetailView.as_view(), name='wifi-environments-detail'),
    path('device/<str:device_id>/geofence-logs/', GeoFenceLogListView.as_view(), name='geofence-logs'),
    path('webhook/sms/', SmsWebhookView.as_view(), name='sms-webhook'),
]
