import traceback
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betterfind_django.settings')
django.setup()

from telemetry.models import Device
from telemetry.views import TrackDataView
from rest_framework.test import APIRequestFactory

factory = APIRequestFactory()
payload = {
    'device': {'device_id': Device.objects.first().device_id}, 
    'timestamp': '2026-02-21T11:23:33Z', 
    'location': {
        'gps': {'enabled': True, 'latitude': 10.6300064, 'longitude': 76.20677, 'accuracy_m': 15.75, 'provider': 'gps'}, 
        'cell_tower': {'mcc': 404, 'mnc': 19, 'lac': 54905, 'cell_id': 206361100, 'network_type': 'LTE', 'signal_strength_dbm': -110, 'neighbor_cells': []}, 
        'wifi_fingerprint': {'connected': True, 'networks': [{'ssid': 'SANAL', 'bssid': '00:00:00:00:00:00', 'rssi_dbm': -58, 'frequency_mhz': 2427, 'security': 'WPA2'}]}
    }, 
    'battery': {'level_percent': 37, 'charging': False, 'power_saver': False}, 
    'network': {'connection_type': 'WiFi', 'internet_available': True}, 
    'sim': {'operator_name': 'Idea', 'operator_code': '40419', 'sim_state': 'READY', 'subscription_id': 'sub_01'}, 
    'events': [{'type': 'REBOOT', 'description': 'test', 'timestamp': '2026-02-21T11:23:33Z'}]
}

request = factory.post('/api/track/', payload, format='json')
view = TrackDataView.as_view()

try:
    response = view(request)
    print("STATUS:", response.status_code)
    print("DATA:", response.data)
except Exception as e:
    traceback.print_exc()
