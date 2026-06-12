import math
from telemetry.models import GeoFence, GeoFenceLog, SecurityAlert

def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371000  # Earth radius in meters

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi/2) ** 2 +
         math.cos(phi1) * math.cos(phi2) *
         math.sin(delta_lambda/2) ** 2)

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    return R * c

def point_in_polygon(lon, lat, poly):
    x, y = lon, lat
    inside = False
    n = len(poly)
    if n == 0:
        return False
    p1x, p1y = poly[0]
    for i in range(1, n + 1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xints = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xints:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def is_point_in_geojson(lat, lng, geojson):
    if not geojson or not isinstance(geojson, dict):
        return False
    
    geom_type = geojson.get("type", "")
    coords = geojson.get("coordinates", [])
    if not geom_type or not coords:
        return False
        
    polygons = []
    if geom_type == "Polygon":
        polygons = [coords]
    elif geom_type == "MultiPolygon":
        polygons = coords
    else:
        return False
        
    for poly in polygons:
        if not poly: continue
        outer_ring = poly[0]
        if point_in_polygon(lng, lat, outer_ring):
            in_hole = False
            for hole in poly[1:]:
                if point_in_polygon(lng, lat, hole):
                    in_hole = True
                    break
            if not in_hole:
                return True
    return False

def check_geofences(device, lat, lng, location_accuracy=None):
    if not lat or not lng:
        return False
        
    fences = GeoFence.objects.filter(device=device, is_active=True)
    if not fences.exists():
        # Check if there are account-level fences (device=None)
        fences = GeoFence.objects.filter(owner=device.owner, device__isnull=True, is_active=True)
        if not fences.exists():
            return False

    in_danger_zone = False

    for fence in fences:
        if fence.polygon:
            is_inside = is_point_in_geojson(lat, lng, fence.polygon)
        else:
            distance = calculate_distance(lat, lng, fence.latitude, fence.longitude)
            
            # Increase allowed margin if accuracy is low (like tower accuracy)
            effective_radius = fence.radius_meters
            if location_accuracy:
                effective_radius += max(0, location_accuracy - 50) # Allow standard GPS slop
                
            is_inside = distance <= effective_radius
        
        if is_inside and fence.last_status != "INSIDE":
            GeoFenceLog.objects.create(
                device=device,
                geofence=fence,
                event_type="ENTER",
                latitude=lat,
                longitude=lng
            )
            fence.last_status = "INSIDE"
            fence.save()
            
            # Logic for DANGER vs SAFE zones
            if fence.zone_type == GeoFence.ZoneType.DANGER:
                SecurityAlert.objects.create(
                    device=device,
                    alert_type=SecurityAlert.AlertType.GEOFENCE_VIOLATION,
                    severity=SecurityAlert.SeverityType.CRITICAL,
                    message=f"🚨 DEVICE ENTERED DANGER ZONE: {fence.name}"
                )
            else:
                SecurityAlert.objects.create(
                    device=device,
                    alert_type=SecurityAlert.AlertType.GEOFENCE_VIOLATION,
                    severity=SecurityAlert.SeverityType.LOW,
                    message=f"Device entered safe zone: {fence.name}"
                )
                
        elif not is_inside and fence.last_status != "OUTSIDE":
            GeoFenceLog.objects.create(
                device=device,
                geofence=fence,
                event_type="EXIT",
                latitude=lat,
                longitude=lng
            )
            fence.last_status = "OUTSIDE"
            fence.save()
            
            if fence.zone_type == GeoFence.ZoneType.DANGER:
                SecurityAlert.objects.create(
                    device=device,
                    alert_type=SecurityAlert.AlertType.GEOFENCE_VIOLATION,
                    severity=SecurityAlert.SeverityType.LOW,
                    message=f"Device safely exited danger zone: {fence.name}"
                )
            else:
                SecurityAlert.objects.create(
                    device=device,
                    alert_type=SecurityAlert.AlertType.GEOFENCE_VIOLATION,
                    severity=SecurityAlert.SeverityType.HIGH,
                    message=f"Device exited safe zone: {fence.name}"
                )
                
        # Determine if currently in danger
        if is_inside and fence.zone_type == GeoFence.ZoneType.DANGER:
            in_danger_zone = True

    return in_danger_zone
