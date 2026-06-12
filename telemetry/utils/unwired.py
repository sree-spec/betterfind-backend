import requests
from django.conf import settings
from telemetry.models import CellTower

UNWIRED_URL = "https://us1.unwiredlabs.com/v2/process.php"

def get_cached_or_fetch(mcc, mnc, lac, cid, neighbor_cells=None):
    # Check cache first. We check if estimated_latitude is not null per your existing DB format.
    existing = CellTower.objects.filter(
        mcc=mcc,
        mnc=mnc,
        lac=lac,
        cid=cid,
        estimated_latitude__isnull=False
    ).first()

    if existing:
        return {
            "latitude": existing.estimated_latitude,
            "longitude": existing.estimated_longitude,
            "accuracy": getattr(existing, 'accuracy', None) or 350
        }

    return get_tower_location(mcc, mnc, lac, cid, neighbor_cells)


def get_tower_location(mcc, mnc, lac, cid, neighbor_cells=None):
    api_key = getattr(settings, 'UNWIREDLABS_API_KEY', '')
    
    # Base active cell
    cells = [
        {
            "lac": int(lac),
            "cid": int(cid)
        }
    ]
    
    # Optional performance upgrade: append neighbor cells to improve triangulated accuracy payload
    if neighbor_cells and isinstance(neighbor_cells, list):
        for cell in neighbor_cells:
            # handle case where the dict might have different keys or missing values gracefully
            n_lac = cell.get('lac')
            n_cid = cell.get('cid') or cell.get('cell_id')
            if n_lac and n_cid:
                cells.append({
                    "lac": int(n_lac),
                    "cid": int(n_cid)
                })

    payload = {
        "token": api_key,
        "radio": "lte",
        "mcc": int(mcc),
        "mnc": int(mnc),
        "cells": cells,
        "address": 1
    }

    try:
        response = requests.post(UNWIRED_URL, json=payload, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "ok" and data.get("lat") and data.get("lon"):
                return {
                    "latitude": data.get("lat"),
                    "longitude": data.get("lon"),
                    "accuracy": data.get("accuracy")
                }
    except Exception as e:
        print("Unwired API error:", e)
        
    return None
