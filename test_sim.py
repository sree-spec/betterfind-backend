import json
from django.test import RequestFactory
from telemetry.views import TrackDataView
from telemetry.models import Device, SimLog, SimSecurityEvent
from core.models import User

# Create a user and device
user, _ = User.objects.get_or_create(email="test@example.com", defaults={"role": "OWNER"})
device, _ = Device.objects.get_or_create(device_id="DEV-0001", defaults={"owner": user, "nickname": "Test Device"})

# Clear past events for clean test
SimSecurityEvent.objects.filter(device=device).delete()
SimLog.objects.filter(device=device).delete()
device.primary_operator_code = None
device.save()

factory = RequestFactory()
view = TrackDataView.as_view()

print("--- Test 1: Baseline Registration ---")
payload1 = {
    "device": {"device_id": "DEV-0001"},
    "sim": {
        "operator": "Idea",
        "operator_code": "40419",
        "mcc": 404,
        "mnc": 19,
        "sim_state": "READY",
        "subscription_id": "sub_01",
        "serial": "123456789"
    }
}
req1 = factory.post('/api/track/', data=json.dumps(payload1), content_type='application/json')
res1 = view(req1)
print("Response:", res1.status_code)
d = Device.objects.get(device_id="DEV-0001")
print("Baseline established:", d.primary_operator_name, d.primary_operator_code)


print("\n--- Test 2: SIM Swap Detection ---")
payload2 = {
    "device": {"device_id": "DEV-0001"},
    "sim": {
        "operator": "Airtel",
        "operator_code": "40410",
        "mcc": 404,
        "mnc": 10,
        "sim_state": "READY",
        "subscription_id": "sub_02",
        "serial": "987654321"
    }
}
req2 = factory.post('/api/track/', data=json.dumps(payload2), content_type='application/json')
res2 = view(req2)
print("Response:", res2.status_code)

print("\n--- Test 3: SIM Removal Detection ---")
payload3 = {
    "device": {"device_id": "DEV-0001"},
    "sim": {
        "sim_state": "ABSENT",
        "operator": "",
        "operator_code": "",
        "mcc": None,
        "mnc": None
    }
}
req3 = factory.post('/api/track/', data=json.dumps(payload3), content_type='application/json')
res3 = view(req3)

print("\n--- Test 4: Country Change & Network Mismatch ---")
payload4 = {
    "device": {"device_id": "DEV-0001"},
    "sim": {
        "operator": "T-Mobile",
        "operator_code": "310260",
        "mcc": 310,
        "mnc": 260,
        "sim_state": "READY"
    },
    "location": {
        "cell_tower": {
            "mcc": 404,
            "mnc": 19,
            "lac": 100,
            "cell_id": 200
        }
    }
}
req4 = factory.post('/api/track/', data=json.dumps(payload4), content_type='application/json')
res4 = view(req4)

print("\n=== Event Results ===")
events = SimSecurityEvent.objects.filter(device=device).order_by('timestamp')
for ev in events:
    print(f"[{ev.risk_level}] {ev.event_type}: {ev.description}")
