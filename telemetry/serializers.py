from rest_framework import serializers
from .models import Device, GeoFence, GpsLocation, CellTower, WiFiScan, SimLog, BatteryLog, DeviceEvent, SecurityAlert, KnownWiFiEnvironment, SimSecurityEvent

class DeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Device
        fields = ['device_id', 'nickname', 'model_name', 'registered_at', 'is_active']

class LinkDeviceSerializer(serializers.Serializer):
    device_id = serializers.CharField(max_length=255)
    nickname = serializers.CharField(max_length=255, required=False, allow_blank=True)
    model_name = serializers.CharField(max_length=255, required=False, allow_blank=True)

class SecurityAlertSerializer(serializers.ModelSerializer):
    class Meta:
        model = SecurityAlert
        fields = '__all__'

class CellTowerSerializer(serializers.ModelSerializer):
    class Meta:
        model = CellTower
        fields = '__all__'

class WiFiScanSerializer(serializers.ModelSerializer):
    class Meta:
        model = WiFiScan
        fields = '__all__'

class SimLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimLog
        fields = '__all__'

class GeoFenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = GeoFence
        fields = '__all__'

class GpsLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = GpsLocation
        fields = '__all__'

class KnownWiFiEnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = KnownWiFiEnvironment
        fields = '__all__'

class SimSecurityEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = SimSecurityEvent
        fields = '__all__'
