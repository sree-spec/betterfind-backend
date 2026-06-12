import os
import sys
import django

# Setup Django environment
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betterfind_django.settings')
django.setup()

from telemetry.utils.unwired import get_tower_location

def test():
    # Example cell data that the user provided
    mcc = 404
    mnc = 19
    lac = 54905
    cid = 118034187
    
    print(f"Testing UnwiredLabs API for MCC={mcc}, MNC={mnc}, LAC={lac}, CID={cid}...")
    result = get_tower_location(mcc, mnc, lac, cid)
    
    if result:
        print("✅ SUCCESS!")
        print(f"Latitude: {result.get('latitude')}")
        print(f"Longitude: {result.get('longitude')}")
        print(f"Accuracy: {result.get('accuracy')} meters")
    else:
        print("❌ FAILED to get location. Check API key or cell data validity.")

if __name__ == "__main__":
    test()
