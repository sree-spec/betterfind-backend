import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

def print_result(name, success, details=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"{status} - {name}")
    if details:
        print(f"   {details}")

def run_tests():
    print("🚀 Starting API Verification for Flutter App Integration...")
    
    # 1. Register User
    email = f"fluttertest_{int(time.time())}@example.com"
    password = "password123"
    register_data = {
        "email": email,
        "password": password,
        "name": "Flutter Test User",
        "role": "OWNER"
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/register", json=register_data)
        if response.status_code == 201:
            print_result("Register User", True, f"Created {email}")
        else:
            print_result("Register User", False, f"Status: {response.status_code}, Body: {response.text}")
            return
    except Exception as e:
        print_result("Register User", False, f"Connection Failed: {e}")
        return

    # 2. Login User
    login_data = {
        "email": email,
        "password": password
    }
    
    try:
        response = requests.post(f"{BASE_URL}/auth/login", json=login_data)
        if response.status_code == 200:
            data = response.json()
            if "accessToken" in data and "user" in data:
                print_result("Login User", True, "Received access token and user object")
                access_token = data['accessToken']
                user_id = data['user']['id']
            else:
                print_result("Login User", False, f"Missing fields in response: {data.keys()}")
                return
        else:
            print_result("Login User", False, f"Status: {response.status_code}, Body: {response.text}")
            return
    except Exception as e:
        print_result("Login User", False, f"Connection Failed: {e}")
        return

    # 3. Ingest Data
    headers = {"Authorization": f"Bearer {access_token}"}
    device_id = "test-device-flutter-001"
    payload = {
        "battery": 85,
        "location": {"lat": 12.9716, "lng": 77.5946},
        "signal": -70
    }
    
    ingest_data = {
        "deviceId": device_id,
        "payload": payload
    }
    
    try:
        response = requests.post(f"{BASE_URL}/data/ingest", json=ingest_data, headers=headers)
        if response.status_code == 201:
            print_result("Ingest Data", True)
        else:
            print_result("Ingest Data", False, f"Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        print_result("Ingest Data", False, f"Connection Failed: {e}")

    # 4. Fetch Latest Data
    try:
        response = requests.get(f"{BASE_URL}/data/latest", headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data.get('deviceId') == device_id and data.get('payload') == payload:
                print_result("Fetch Latest Data", True, "Matched deviceId and payload")
            else:
                print_result("Fetch Latest Data", False, f"Data mismatch: {data}")
        else:
            print_result("Fetch Latest Data", False, f"Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        print_result("Fetch Latest Data", False, f"Connection Failed: {e}")

    # 5. Fetch History
    try:
        response = requests.get(f"{BASE_URL}/data/history?take=5", headers=headers)
        if response.status_code == 200:
            data = response.json()
            # history view returns a list (ListAPIView with pagination disabled? No, ListAPIView paginates if default pagination is set.
            # My view returns queryset slice which DRF might serialize as list if pagination class is None.
            # Let's assume list for now based on implementation `return queryset[skip:take]`.
            # Wait, `ListAPIView` calls `list` -> `paginate_queryset` -> `get_serializer`.
            # My implementation overrides `get_queryset` but returns a sliced list.
            # `ListAPIView` will try to paginate `get_queryset()` result.
            # But `get_queryset` returns a list (slice of queryset evaluates to list?). No, slice returns new QuerySet or list.
            # Actually, `queryset[k:n]` returns a new QuerySet if step is None.
            # So `ListAPIView` might work.
            # But let's verify response type.
            if isinstance(data, list) or 'results' in data: # pagination
                print_result("Fetch History", True, f"Received {len(data)} items")
            else:
                print_result("Fetch History", False, f"Unexpected format: {type(data)}")
        else:
            print_result("Fetch History", False, f"Status: {response.status_code}, Body: {response.text}")
    except Exception as e:
        print_result("Fetch History", False, f"Connection Failed: {e}")

if __name__ == "__main__":
    run_tests()
