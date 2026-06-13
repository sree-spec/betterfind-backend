from rest_framework import generics, status, permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.db import models
import requests
from telemetry.utils.unwired import get_cached_or_fetch
from telemetry.utils.geofence import check_geofences

from .models import Device, GeoFence, GeoFenceLog, GpsLocation, CellTower, WiFiScan, SimLog, BatteryLog, DeviceEvent, SecurityAlert, KnownWiFiEnvironment, SimSecurityEvent
from .serializers import DeviceSerializer, LinkDeviceSerializer, SecurityAlertSerializer, CellTowerSerializer, WiFiScanSerializer, SimLogSerializer, GpsLocationSerializer, GeoFenceSerializer, KnownWiFiEnvironmentSerializer, SimSecurityEventSerializer
from core.models import User

class LinkDeviceView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = LinkDeviceSerializer(data=request.data)
        if serializer.is_valid():
            device_id = serializer.validated_data['device_id']
            nickname = serializer.validated_data.get('nickname', '')
            model_name = serializer.validated_data.get('model_name', '')

            device, created = Device.objects.get_or_create(
                device_id=device_id,
                defaults={
                    'owner': request.user,
                    'nickname': nickname or f'Device ({device_id})',
                    'model_name': model_name
                }
            )

            if not created:
                if device.owner == request.user:
                    # Re-linking own device — just confirm
                    return Response({"message": "Device linked successfully", "device": DeviceSerializer(device).data}, status=status.HTTP_200_OK)

                # Check if this device is owned by the system sentinel (auto-registered, unclaimed)
                if device.owner.email == 'system@betterfind.internal':
                    # Claim it: transfer real ownership to this user
                    device.owner = request.user
                    device.nickname = nickname or f'Device ({device_id})'
                    device.save()
                    return Response({"message": "Device claimed successfully", "device": DeviceSerializer(device).data}, status=status.HTTP_200_OK)

                # Device is owned by someone else — add caller as a watcher
                device.watched_by.add(request.user)
                return Response({"message": "Now watching device", "device": DeviceSerializer(device).data}, status=status.HTTP_200_OK)

            # Newly created — this user is the owner
            return Response({"message": "Device linked successfully", "device": DeviceSerializer(device).data}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TrackDataView(APIView):
    # Depending on how the flutter app sends data, it might use a token, or just raw device_id.
    # Allowing any for raw ingestion, but in production should require a device token or signature.
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        payload = request.data
        device_info = payload.get('device', {})
        device_id = device_info.get('device_id') or payload.get('deviceId')

        if not device_id:
            return Response({"error": "Missing device_id"}, status=status.HTTP_400_BAD_REQUEST)

        device = Device.objects.filter(device_id=device_id).first()
        if not device:
            # Auto-register the device on first telemetry contact.
            # This handles the case where the friend's phone never successfully
            # called /api/device/link/ (e.g. was offline at the time).
            # We create a bare device record; the owner will be claimed via
            # /api/device/link/ when the watcher or the device owner enters the code.
            # Use a sentinel system user (or None owner trick via nullable FK).
            # Since owner is non-nullable, we use get_or_create on a system user.
            from django.contrib.auth import get_user_model
            UserModel = get_user_model()
            system_user, _ = UserModel.objects.get_or_create(
                email='system@betterfind.internal',
                defaults={
                    'username': 'system_betterfind',
                    'is_active': False,
                    'role': UserModel.Role.ADMIN,
                }
            )
            device = Device.objects.create(
                device_id=device_id,
                owner=system_user,
                nickname=f'Auto-registered ({device_id})',
                model_name=device_info.get('model', ''),
            )
            print(f'📱 Auto-registered new device: {device_id}')

        # Automatically update device's model_name from telemetry info to avoid DB migrations
        mfr = device_info.get('manufacturer')
        model = device_info.get('model')
        os_ver = device_info.get('os_version')
        if mfr or model or os_ver:
            combined = f"{mfr or ''}|{model or ''}|{os_ver or ''}"
            if device.model_name != combined:
                device.model_name = combined
                device.save()

        now = timezone.now()

        # GPS Location & Geofence Checking
        loc_data = payload.get('location', {}).get('gps', {})
        if loc_data and loc_data.get('latitude') and loc_data.get('longitude'):
            lat = loc_data.get('latitude')
            lng = loc_data.get('longitude')
            GpsLocation.objects.create(
                device=device,
                latitude=lat,
                longitude=lng,
                accuracy=loc_data.get('accuracy'),
                altitude=loc_data.get('altitude'),
                speed=loc_data.get('speed'),
                heading=loc_data.get('heading'),
                timestamp=self._parse_time(loc_data.get('timestamp'), now)
            )

            # Check Geofences (handles both custom polygons and radius circles)
            check_geofences(device, lat, lng, loc_data.get('accuracy'))

        # Cell Tower
        cell_data = payload.get('location', {}).get('cell_tower')
        if cell_data:
            est_lat, est_lng, est_acc = None, None, None
            
            # 1. Try to get exact tower location
            mcc = cell_data.get('mcc')
            mnc = cell_data.get('mnc')
            lac = cell_data.get('lac')
            cid = cell_data.get('cell_id')
            neighbor_cells = cell_data.get('neighbor_cells', [])
            
            if mcc and mnc and lac and cid:
                tower_res = get_cached_or_fetch(mcc, mnc, lac, cid, neighbor_cells)
                if tower_res:
                    est_lat = tower_res.get('latitude')
                    est_lng = tower_res.get('longitude')
                    est_acc = tower_res.get('accuracy')

            # 2. Fallback to current device GPS if tower API fails
            if not est_lat and loc_data and loc_data.get('latitude') and loc_data.get('longitude'):
                est_lat = loc_data.get('latitude')
                est_lng = loc_data.get('longitude')
            
            CellTower.objects.create(
                device=device,
                mcc=mcc,
                mnc=mnc,
                lac=lac,
                cid=cid,
                dbm=cell_data.get('signal_strength_dbm'),
                network_type=cell_data.get('network_type'),
                estimated_latitude=est_lat,
                estimated_longitude=est_lng,
                accuracy=est_acc,
                timestamp=self._parse_time(payload.get('timestamp'), now)
            )

            # Check geofences using tower location if GPS wasn't already checked
            if est_lat and est_lng and not (loc_data and loc_data.get('latitude') and loc_data.get('longitude')):
                check_geofences(device, est_lat, est_lng, est_acc)

        # Determine best available location for cross-checks (Wi-Fi, Security Alerts)
        best_lat, best_lng, best_acc = None, None, None

        if loc_data and loc_data.get('latitude'):
            best_lat = loc_data.get('latitude')
            best_lng = loc_data.get('longitude')
            best_acc = loc_data.get('accuracy')
        elif 'est_lat' in locals() and est_lat:
            best_lat = est_lat
            best_lng = est_lng
            best_acc = est_acc

        # WiFi
        wifi_list = payload.get('location', {}).get('wifi_fingerprint', {}).get('networks', [])
        scanned_bssids = set([w.get('bssid') for w in wifi_list if w.get('bssid')])

        for wifi_data in wifi_list:
            WiFiScan.objects.create(
                device=device,
                bssid=wifi_data.get('bssid'),
                ssid=wifi_data.get('ssid'),
                signal_strength=wifi_data.get('rssi_dbm'),
                timestamp=self._parse_time(payload.get('timestamp'), now)
            )

        if scanned_bssids:
            known_envs = KnownWiFiEnvironment.objects.filter(device=device, is_active=True)
            highest_confidence = 0.0
            best_env = None

            for env in known_envs:
                env_bssids = set(env.bssids)
                if not env_bssids:
                    continue
                match_count = len(scanned_bssids.intersection(env_bssids))
                confidence = match_count / len(env_bssids)
                if confidence > highest_confidence:
                    highest_confidence = confidence
                    best_env = env

            if highest_confidence < 0.40 and known_envs.exists():
                # SECURITY LOGIC: Device is near an unknown Wi-Fi. 
                # Let's verify with GPS if it actually moved away from its known environments.
                is_actually_away = True
                
                # If we got GPS or estimated Tower location in this payload, check distance
                if best_lat and best_lng:
                    from telemetry.utils.geofence import calculate_distance
                    
                    for env in known_envs:
                        # Find the first GPS location we ever recorded while connected to this known env
                        # (A simple heuristic to find the env's physical location)
                        first_scan = WiFiScan.objects.filter(device=device, bssid__in=env.bssids).order_by('timestamp').first()
                        if first_scan:
                            # Try to find a GPS point around the same time this env was scanned
                            nearby_gps = GpsLocation.objects.filter(
                                device=device, 
                                timestamp__gte=first_scan.timestamp - timezone.timedelta(minutes=5),
                                timestamp__lte=first_scan.timestamp + timezone.timedelta(minutes=5)
                            ).first()
                            
                            if nearby_gps:
                                dist = calculate_distance(best_lat, best_lng, nearby_gps.latitude, nearby_gps.longitude)
                                if dist < 200: # Within 200 meters of the known environment's physical location
                                    is_actually_away = False
                                    break
                
                if is_actually_away:
                    if not SecurityAlert.objects.filter(
                        device=device,
                        alert_type=SecurityAlert.AlertType.UNKNOWN_WIFI,
                        is_resolved=False
                    ).exists():
                        SecurityAlert.objects.create(
                            device=device,
                            alert_type=SecurityAlert.AlertType.UNKNOWN_WIFI,
                            is_resolved=False,
                            severity=SecurityAlert.SeverityType.MEDIUM,
                            message=f"Location change verified by GPS: Device moved to unknown Wi-Fi environment. Highest match: {highest_confidence*100:.1f}%"
                        )

        # SIM Log & Change Detection
        sim_data = payload.get('sim')
        if sim_data:
            new_operator = sim_data.get('operator')
            new_operator_code = sim_data.get('operator_code')
            new_mcc = sim_data.get('mcc')
            new_mnc = sim_data.get('mnc')
            new_sim_state = sim_data.get('sim_state')
            new_sub_id = sim_data.get('subscription_id')
            new_serial = sim_data.get('serial')

            last_sim = device.sim_logs.first()

            # Baseline Update
            if not device.primary_operator_code and new_operator_code:
                device.primary_operator_name = new_operator
                device.primary_operator_code = new_operator_code
                device.primary_mcc = new_mcc
                device.primary_mnc = new_mnc
                device.save()

            # Security Events Storage List
            new_events = []

            if new_sim_state == "ABSENT":
                new_events.append(SimSecurityEvent(device=device, event_type=SimSecurityEvent.EventType.SIM_REMOVED, risk_level=SimSecurityEvent.RiskLevel.CRITICAL, description="SIM card removed from device."))
            
            if device.primary_operator_code and new_operator_code and str(new_operator_code) != str(device.primary_operator_code):
                new_events.append(SimSecurityEvent(device=device, event_type=SimSecurityEvent.EventType.SIM_CHANGED, risk_level=SimSecurityEvent.RiskLevel.HIGH, description=f"SIM changed from {device.primary_operator_name} to {new_operator}."))

            if device.primary_mcc and new_mcc and str(new_mcc) != str(device.primary_mcc):
                new_events.append(SimSecurityEvent(device=device, event_type=SimSecurityEvent.EventType.COUNTRY_CHANGED, risk_level=SimSecurityEvent.RiskLevel.HIGH, description=f"Country changed. MCC from {device.primary_mcc} to {new_mcc}."))

            if cell_data:
                tower_mcc = cell_data.get('mcc')
                tower_mnc = cell_data.get('mnc')
                if tower_mcc and new_mcc and tower_mnc and new_mnc:
                    if str(tower_mcc) != str(new_mcc) or str(tower_mnc) != str(new_mnc):
                        new_events.append(SimSecurityEvent(device=device, event_type=SimSecurityEvent.EventType.NETWORK_MISMATCH, risk_level=SimSecurityEvent.RiskLevel.HIGH, description=f"SIM MCC/MNC ({new_mcc}/{new_mnc}) mismatch Tower ({tower_mcc}/{tower_mnc})."))

            one_hour_ago = now - timezone.timedelta(hours=1)
            recent_sims_count = device.sim_logs.filter(timestamp__gte=one_hour_ago).values('operator_code').distinct().count()
            if recent_sims_count >= 3:
                recent_alert = SimSecurityEvent.objects.filter(device=device, event_type=SimSecurityEvent.EventType.SUSPICIOUS_SWITCHING, timestamp__gte=one_hour_ago).exists()
                if not recent_alert:
                    new_events.append(SimSecurityEvent(device=device, event_type=SimSecurityEvent.EventType.SUSPICIOUS_SWITCHING, risk_level=SimSecurityEvent.RiskLevel.MEDIUM, description="High rate of operator switching detected."))

            last_reboot = device.events.filter(event_type=DeviceEvent.EventType.REBOOT).order_by('-timestamp').first()
            if last_reboot and last_sim:
                if (now - last_reboot.timestamp).total_seconds() < 300 and new_operator_code != last_sim.operator_code:
                    new_events.append(SimSecurityEvent(device=device, event_type=SimSecurityEvent.EventType.SIM_CHANGED, risk_level=SimSecurityEvent.RiskLevel.CRITICAL, description="CRITICAL: SIM swap matching device reboot window."))

            if new_events:
                SimSecurityEvent.objects.bulk_create(new_events)

            SimLog.objects.create(
                device=device,
                operator_name=new_operator,
                operator_code=new_operator_code,
                mcc=new_mcc,
                mnc=new_mnc,
                sim_state=new_sim_state,
                subscription_id=new_sub_id,
                sim_serial_number=new_serial,
                timestamp=self._parse_time(payload.get('timestamp'), now)
            )

        # Battery
        battery_data = payload.get('battery')
        if battery_data and battery_data.get('level_percent') is not None:
            BatteryLog.objects.create(
                device=device,
                level=battery_data.get('level_percent'),
                is_charging=battery_data.get('is_charging', False),
                timestamp=self._parse_time(payload.get('timestamp'), now)
            )

        # Events (Reboots, etc.)
        events = payload.get('events', [])
        for event in events:
            DeviceEvent.objects.create(
                device=device,
                event_type=event.get('type', DeviceEvent.EventType.OTHER),
                description=event.get('description', ''),
                timestamp=self._parse_time(payload.get('timestamp'), now)
            )
            
        # specifically check the new device_events sub-payload for force offline
        device_events_payload = payload.get('device_events', {})
        if device_events_payload.get('force_offline'):
            DeviceEvent.objects.create(
                device=device,
                event_type=DeviceEvent.EventType.OTHER,
                description='force_offline explicitly triggered',
                timestamp=now
            )

        in_danger_zone = False

        if best_lat and best_lng:
            in_danger_zone = check_geofences(device, best_lat, best_lng, best_acc)

        return Response({
            "status": "Data successfully ingested",
            "in_danger_zone": in_danger_zone
        }, status=status.HTTP_201_CREATED)

    def _parse_time(self, ts_str, default_now):
        if not ts_str:
            return default_now
        try:
            return parse_datetime(ts_str)
        except Exception:
            return default_now

class SmsWebhookView(APIView):
    # Twilio (or other SMS providers) webhooks do not use our app's authentication
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        # We handle Twilio-style form data, or JSON depending on the provider.
        # Twilio sends form data: request.POST
        body = request.data.get('Body') or request.POST.get('Body', '')
        from_number = request.data.get('From') or request.POST.get('From', '')

        if not body:
            return Response({"error": "No body provided"}, status=status.HTTP_400_BAD_REQUEST)

        # Expected format: ID:DEVICE_ID,Lat:12.34,Lng:56.78,Bat:80
        # Parse the comma-separated key:value pairs
        parsed_data = {}
        parts = body.split(',')
        for part in parts:
            if ':' in part:
                k, v = part.split(':', 1)
                parsed_data[k.strip().upper()] = v.strip()

        device_id = parsed_data.get('ID')
        if not device_id:
            return Response({"error": "Missing device ID in SMS payload"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            device = Device.objects.get(device_id=device_id)
        except Device.DoesNotExist:
            return Response({"error": "Device not found"}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()

        lat_str = parsed_data.get('LAT')
        lng_str = parsed_data.get('LNG')
        
        if lat_str and lng_str:
            try:
                lat = float(lat_str)
                lng = float(lng_str)
                
                # We store an SMS location as a GPS location (with high accuracy since we assume it's from GPS hardware)
                # But we could also add a flag or note indicating it came via SMS fallback
                GpsLocation.objects.create(
                    device=device,
                    latitude=lat,
                    longitude=lng,
                    accuracy=50.0, # Estimated since we strip it to save SMS space
                    timestamp=now
                )
                
                # Check Geofences
                check_geofences(device, lat, lng, 50.0)
            except ValueError:
                pass # Invalid float

        bat_str = parsed_data.get('BAT')
        if bat_str:
            try:
                bat_level = int(bat_str.replace('%', ''))
                BatteryLog.objects.create(
                    device=device,
                    level=bat_level,
                    is_charging=False, # We don't know, default to False
                    timestamp=now
                )
            except ValueError:
                pass

        # Also register a device event that SMS fallback was used
        DeviceEvent.objects.create(
            device=device,
            event_type=DeviceEvent.EventType.OTHER,
            description=f'SMS Fallback received from {from_number}',
            timestamp=now
        )

        # Twilio requires valid XML TwiML responses, or just a 200 OK string
        # A simple 200 OK is usually enough to stop retries if the provider accepts JSON
        return Response({"status": "SMS processed"}, status=status.HTTP_200_OK)

class LatestDataView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, device_id):
        # Verify access: user must be the owner OR an authorized watcher
        try:
            device = Device.objects.get(device_id=device_id)
            is_owner = device.owner == request.user
            is_watcher = device.watched_by.filter(pk=request.user.pk).exists()
            if not is_owner and not is_watcher:
                return Response({"error": "Access denied. Enter the device code first to start watching."}, status=status.HTTP_403_FORBIDDEN)
        except Device.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Check if the device is explicitly forcing offline (stopped tracking recently)
        recent_offline_event = device.events.filter(
            event_type=DeviceEvent.EventType.OTHER, 
            description='Tracking Stopped explicitly' # We will check this if added, or rely on shutdown
        ).order_by('-timestamp').first()
        
        # Or look at the raw device payload we will inject an event for
        # Wait, the app sends: data['device_events']['force_offline'] = true
        # This goes into TrackDataView events array if formatted properly, but app sent it directly in the data object.
        # Let's check device.events for recent shutdowns.
        recent_shutdown = device.events.filter(
            description__icontains='force_offline',
        ).order_by('-timestamp').first()

        force_offline = False
        if recent_shutdown and (timezone.now() - recent_shutdown.timestamp).total_seconds() < 120:
             force_offline = True

        # Tracking Source Priority Logic — allow up to 5 minutes before going OFFLINE
        latest_gps = device.gps_locations.order_by('-timestamp').first()
        latest_cell = device.cell_towers.order_by('-timestamp').first()
        
        location_data = None
        source = 'OFFLINE'
        
        if latest_gps and (timezone.now() - latest_gps.timestamp).total_seconds() < 300:  # 5 min
            location_data = {"lat": latest_gps.latitude, "lng": latest_gps.longitude, "accuracy": latest_gps.accuracy}
            source = 'GPS'
        elif latest_cell and latest_cell.estimated_latitude and (timezone.now() - latest_cell.timestamp).total_seconds() < 300:
            location_data = {"lat": latest_cell.estimated_latitude, "lng": latest_cell.estimated_longitude, "accuracy": 1000}
            source = 'CELL_TOWER'

        # Always return last known battery (don't discard based on age)
        battery = device.battery_logs.order_by('-timestamp').first()

        # Always return last known SIM (don't discard based on age)
        sim = device.sim_logs.order_by('-timestamp').first()
            
        if force_offline:
            location_data = None
            source = 'OFFLINE'

        alerts = device.security_alerts.filter(is_resolved=False).order_by('-created_at')[:5]

        # Calculate SIM Risk Score
        risk_score = 0
        recent_sim_events = device.sim_security_events.order_by('-timestamp')[:5]
        for ev in recent_sim_events:
            if ev.risk_level == SimSecurityEvent.RiskLevel.CRITICAL: risk_score += 80
            elif ev.risk_level == SimSecurityEvent.RiskLevel.HIGH: risk_score += 60
            elif ev.risk_level == SimSecurityEvent.RiskLevel.MEDIUM: risk_score += 40
            else: risk_score += 10
        
        sim_status = "Normal"
        if risk_score >= 100: sim_status = "Critical"
        elif risk_score >= 60: sim_status = "Suspicious"
        
        sim_data = None
        if sim or device.primary_operator_code:
             sim_data = {
                 "operator": sim.operator_name if sim else (device.primary_operator_name or "Unknown"),
                 "mcc": sim.mcc if sim else device.primary_mcc,
                 "mnc": sim.mnc if sim else device.primary_mnc,
                 "state": sim.sim_state if sim else "UNKNOWN",
                 "status": sim_status,
                 "risk_score": min(risk_score, 100)
             }

        # Parse device_info from model_name field (stored as "manufacturer|model|os_version")
        device_info = {}
        if device.model_name:
            parts = device.model_name.split('|')
            device_info = {
                "manufacturer": parts[0].strip() if len(parts) > 0 and parts[0].strip() else "—",
                "model": parts[1].strip() if len(parts) > 1 and parts[1].strip() else "—",
                "android_version": parts[2].strip() if len(parts) > 2 and parts[2].strip() else "—",
            }

        return Response({
            "device": DeviceSerializer(device).data,
            "source": source,
            "location": location_data,
            "battery": {"level": battery.level, "is_charging": battery.is_charging} if battery else None,
            "sim": sim_data,
            "device_info": device_info,
            "alerts": SecurityAlertSerializer(alerts, many=True).data
        })

class DeviceListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        # Return devices the user owns OR is watching
        owned = Device.objects.filter(owner=request.user)
        watching = request.user.watched_devices.all()
        # Combine and deduplicate using union
        devices = (owned | watching).distinct()
        return Response([DeviceSerializer(device).data for device in devices])

class GeoFenceListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_device(self, request, device_id):
        try:
            device = Device.objects.get(device_id=device_id)
            is_owner = device.owner == request.user
            is_watcher = device.watched_by.filter(pk=request.user.pk).exists()
            if not is_owner and not is_watcher:
                return None
            return device
        except Device.DoesNotExist:
            return None

    def get(self, request, device_id):
        device = self._get_device(request, device_id)
        if not device:
            return Response({"error": "Device not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        # Return fences belonging to the device, or owner's global fences
        fences = GeoFence.objects.filter(models.Q(device=device) | models.Q(device__isnull=True, owner=device.owner))
        serializer = GeoFenceSerializer(fences, many=True)
        return Response(serializer.data)

    def post(self, request, device_id):
        device = self._get_device(request, device_id)
        if not device:
            return Response({"error": "Device not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        data['owner'] = request.user.id
        data['device'] = device.id

        serializer = GeoFenceSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class GeoFenceDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_device(self, request, device_id):
        try:
            device = Device.objects.get(device_id=device_id)
            is_owner = device.owner == request.user
            is_watcher = device.watched_by.filter(pk=request.user.pk).exists()
            if not is_owner and not is_watcher:
                return None
            return device
        except Device.DoesNotExist:
            return None

    def delete(self, request, device_id, fence_id):
        device = self._get_device(request, device_id)
        if not device:
            return Response({"error": "Device not found or access denied"}, status=status.HTTP_404_NOT_FOUND)
            
        try:
            fence = GeoFence.objects.get(id=fence_id, device=device)
            fence.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except GeoFence.DoesNotExist:
            return Response({"error": "Geofence not found"}, status=status.HTTP_404_NOT_FOUND)

class DeviceHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_device(self, request, device_id):
        try:
            device = Device.objects.get(device_id=device_id)
            is_owner = device.owner == request.user
            is_watcher = device.watched_by.filter(pk=request.user.pk).exists()
            if not is_owner and not is_watcher:
                return None
            return device
        except Device.DoesNotExist:
            return None

    def get(self, request, device_id, data_type):
        device = self._get_device(request, device_id)
        if not device:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if data_type == 'towers':
            qs = device.cell_towers.order_by('-timestamp')[:50]
            serializer = CellTowerSerializer(qs, many=True)
            return Response(serializer.data)
            
        elif data_type == 'wifi':
            qs = device.wifi_scans.order_by('-timestamp')[:50]
            serializer = WiFiScanSerializer(qs, many=True)
            return Response(serializer.data)
            
        elif data_type == 'sim-logs':
            qs = device.sim_logs.order_by('-timestamp')[:50]
            serializer = SimLogSerializer(qs, many=True)
            return Response(serializer.data)
            
        elif data_type == 'alerts':
            qs = device.security_alerts.order_by('-created_at')[:50]
            serializer = SecurityAlertSerializer(qs, many=True)
            return Response(serializer.data)
            
        elif data_type == 'sim-events':
            qs = device.sim_security_events.order_by('-timestamp')[:50]
            serializer = SimSecurityEventSerializer(qs, many=True)
            return Response(serializer.data)
            
        elif data_type == 'locations':
            qs = device.gps_locations.order_by('-timestamp')[:50]
            serializer = GpsLocationSerializer(qs, many=True)
            return Response(serializer.data)

        return Response({"error": "Invalid data type"}, status=status.HTTP_400_BAD_REQUEST)

class KnownWiFiEnvironmentListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_device(self, request, device_id):
        try:
            device = Device.objects.get(device_id=device_id)
            if request.user.role == User.Role.OWNER and device.owner != request.user:
                return None
            return device
        except Device.DoesNotExist:
            return None

    def get(self, request, device_id):
        device = self._get_device(request, device_id)
        if not device:
            return Response({"error": "Device not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        envs = KnownWiFiEnvironment.objects.filter(device=device)
        serializer = KnownWiFiEnvironmentSerializer(envs, many=True)
        return Response(serializer.data)

    def post(self, request, device_id):
        device = self._get_device(request, device_id)
        if not device:
            return Response({"error": "Device not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        data = request.data.copy()
        data['device'] = device.id

        serializer = KnownWiFiEnvironmentSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class KnownWiFiEnvironmentDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_device(self, request, device_id):
        try:
            device = Device.objects.get(device_id=device_id)
            if request.user.role == User.Role.OWNER and device.owner != request.user:
                return None
            return device
        except Device.DoesNotExist:
            return None
            
    def delete(self, request, device_id, env_id):
        device = self._get_device(request, device_id)
        if not device:
            return Response({"error": "Device not found or access denied"}, status=status.HTTP_404_NOT_FOUND)
            
        try:
            env = KnownWiFiEnvironment.objects.get(id=env_id, device=device)
            env.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except KnownWiFiEnvironment.DoesNotExist:
            return Response({"error": "Environment not found"}, status=status.HTTP_404_NOT_FOUND)


class GeoFenceLogListView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def _get_device(self, request, device_id):
        try:
            device = Device.objects.get(device_id=device_id)
            is_owner = device.owner == request.user
            is_watcher = device.watched_by.filter(pk=request.user.pk).exists()
            if not is_owner and not is_watcher:
                return None
            return device
        except Device.DoesNotExist:
            return None

    def get(self, request, device_id):
        device = self._get_device(request, device_id)
        if not device:
            return Response({"error": "Device not found or access denied"}, status=status.HTTP_404_NOT_FOUND)

        logs = GeoFenceLog.objects.filter(device=device).order_by('-timestamp')[:50]
        data = []
        for log in logs:
            data.append({
                "id": str(log.id),
                "geofence_name": log.geofence.name,
                "event_type": log.event_type,
                "latitude": log.latitude,
                "longitude": log.longitude,
                "timestamp": log.timestamp
            })
        return Response(data, status=status.HTTP_200_OK)

class AdminStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        total_users = User.objects.count()
        total_devices = Device.objects.count()

        fifteen_mins_ago = timezone.now() - timezone.timedelta(minutes=15)
        active_gps_devices = GpsLocation.objects.filter(timestamp__gte=fifteen_mins_ago).values_list('device_id', flat=True)
        active_cell_devices = CellTower.objects.filter(timestamp__gte=fifteen_mins_ago).values_list('device_id', flat=True)
        active_device_ids = set(list(active_gps_devices) + list(active_cell_devices))
        active_devices = len(active_device_ids)

        recent_alerts_qs = SecurityAlert.objects.filter(is_resolved=False).order_by('-created_at')[:10]
        recent_alerts = SecurityAlertSerializer(recent_alerts_qs, many=True).data

        return Response({
            "total_users": total_users,
            "total_devices": total_devices,
            "active_devices": active_devices,
            "recent_alerts": recent_alerts
        }, status=status.HTTP_200_OK)
