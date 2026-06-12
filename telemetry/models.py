from django.db import models
from django.conf import settings
import uuid

class Device(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device_id = models.CharField(max_length=255, unique=True, help_text="ANDROID_ID or generated unique ID")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='devices')
    nickname = models.CharField(max_length=255, null=True, blank=True)
    model_name = models.CharField(max_length=255, null=True, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    primary_operator_name = models.CharField(max_length=100, null=True, blank=True)
    primary_operator_code = models.CharField(max_length=50, null=True, blank=True)
    primary_mcc = models.IntegerField(null=True, blank=True)
    primary_mnc = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return f"{self.nickname or self.model_name or self.device_id} ({self.owner.email})"

class GpsLocation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='gps_locations')
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy = models.FloatField(null=True, blank=True)
    altitude = models.FloatField(null=True, blank=True)
    speed = models.FloatField(null=True, blank=True)
    heading = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

class CellTower(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='cell_towers')
    mcc = models.IntegerField(null=True, blank=True)
    mnc = models.IntegerField(null=True, blank=True)
    lac = models.IntegerField(null=True, blank=True)
    cid = models.BigIntegerField(null=True, blank=True)
    dbm = models.IntegerField(null=True, blank=True)
    network_type = models.CharField(max_length=50, null=True, blank=True)
    estimated_latitude = models.FloatField(null=True, blank=True)
    estimated_longitude = models.FloatField(null=True, blank=True)
    accuracy = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

class WiFiScan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='wifi_scans')
    bssid = models.CharField(max_length=50)
    ssid = models.CharField(max_length=255, null=True, blank=True)
    signal_strength = models.IntegerField(null=True, blank=True)
    frequency = models.IntegerField(null=True, blank=True)
    estimated_latitude = models.FloatField(null=True, blank=True)
    estimated_longitude = models.FloatField(null=True, blank=True)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

class SimLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='sim_logs')
    operator_name = models.CharField(max_length=100, null=True, blank=True)
    operator_code = models.CharField(max_length=50, null=True, blank=True)
    mcc = models.IntegerField(null=True, blank=True)
    mnc = models.IntegerField(null=True, blank=True)
    sim_state = models.CharField(max_length=50, null=True, blank=True)
    subscription_id = models.CharField(max_length=100, null=True, blank=True)
    iso_country_code = models.CharField(max_length=10, null=True, blank=True)
    sim_serial_number = models.CharField(max_length=255, null=True, blank=True)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

class BatteryLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='battery_logs')
    level = models.IntegerField()
    is_charging = models.BooleanField(default=False)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

class DeviceEvent(models.Model):
    class EventType(models.TextChoices):
        REBOOT = 'REBOOT', 'Reboot'
        SHUTDOWN = 'SHUTDOWN', 'Shutdown'
        APP_STARTED = 'APP_STARTED', 'App Started'
        APP_STOPPED = 'APP_STOPPED', 'App Stopped'
        OTHER = 'OTHER', 'Other'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    description = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

class SecurityAlert(models.Model):
    class AlertType(models.TextChoices):
        SIM_CHANGE = 'SIM_CHANGE', 'SIM Changed'
        UNKNOWN_WIFI = 'UNKNOWN_WIFI', 'Unknown Wi-Fi Environment'
        ABNORMAL_TOWER = 'ABNORMAL_TOWER', 'Abnormal Cell Tower Region'
        OFFLINE_LONG = 'OFFLINE_LONG', 'Offline Too Long'
        GEOFENCE_VIOLATION = 'GEOFENCE_VIOLATION', 'Geo-fence Violation'

    class SeverityType(models.TextChoices):
        LOW = 'LOW', 'Low'
        MEDIUM = 'MEDIUM', 'Medium'
        HIGH = 'HIGH', 'High'
        CRITICAL = 'CRITICAL', 'Critical'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='security_alerts')
    alert_type = models.CharField(max_length=50, choices=AlertType.choices)
    severity = models.CharField(max_length=20, choices=SeverityType.choices, default=SeverityType.MEDIUM)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

class GeoFence(models.Model):
    class ZoneType(models.TextChoices):
        SAFE = 'SAFE', 'Safe Zone'
        DANGER = 'DANGER', 'Danger Zone'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='geofences')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='geofences', null=True, blank=True)  # Null means applies to all owner's devices
    name = models.CharField(max_length=255)
    latitude = models.FloatField()
    longitude = models.FloatField()
    radius_meters = models.FloatField()
    polygon = models.JSONField(null=True, blank=True)
    zone_type = models.CharField(max_length=10, choices=ZoneType.choices, default=ZoneType.SAFE)
    last_status = models.CharField(max_length=10, default="UNKNOWN")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.radius_meters}m)"


class GeoFenceLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='geofence_logs')
    geofence = models.ForeignKey(GeoFence, on_delete=models.CASCADE, related_name='logs')
    event_type = models.CharField(max_length=10)  # ENTER / EXIT
    latitude = models.FloatField()
    longitude = models.FloatField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']


class KnownWiFiEnvironment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='known_wifi_envs')
    name = models.CharField(max_length=255)  # e.g., "HOME", "OFFICE", "SAFE ZONE"
    bssids = models.JSONField(default=list, help_text="List of string BSSIDs associated with this environment")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} for {self.device.nickname or getattr(self.device, 'device_id', '')}"


class SimSecurityEvent(models.Model):
    class EventType(models.TextChoices):
        SIM_REMOVED = 'SIM_REMOVED', 'SIM Removed'
        SIM_CHANGED = 'SIM_CHANGED', 'SIM Changed'
        COUNTRY_CHANGED = 'COUNTRY_CHANGED', 'Country Changed'
        NETWORK_MISMATCH = 'NETWORK_MISMATCH', 'Network Mismatch'
        SUSPICIOUS_SWITCHING = 'SUSPICIOUS_SWITCHING', 'Suspicious Switching'

    class RiskLevel(models.TextChoices):
        LOW = 'LOW', 'Low Risk'
        MEDIUM = 'MEDIUM', 'Medium Risk'
        HIGH = 'HIGH', 'High Risk'
        CRITICAL = 'CRITICAL', 'Critical Risk'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='sim_security_events')
    event_type = models.CharField(max_length=50, choices=EventType.choices)
    risk_level = models.CharField(max_length=20, choices=RiskLevel.choices, default=RiskLevel.MEDIUM)
    description = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
