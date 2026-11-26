import json
import os
from functools import lru_cache
from typing import Annotated
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, HTTPException, Query

router = APIRouter()
Latitude = Annotated[float, Query(ge=-90, le=90)]
Longitude = Annotated[float, Query(ge=-180, le=180)]


@lru_cache(maxsize=256)
def fetch_route(coordinates):
    base = os.getenv("KARTEJ_ROUTING_URL", "https://routing.openstreetmap.de/routed-car").rstrip("/")
    url = f"{base}/route/v1/driving/{coordinates}?overview=simplified&geometries=geojson"
    request = Request(url, headers={"User-Agent": "UrganchKartej/1.0"})
    try:
        with urlopen(request, timeout=6) as response:
            result = json.loads(response.read(1_000_000))
        route = result["routes"][0]
        return {
            "points": [[lat, lng] for lng, lat in route["geometry"]["coordinates"]],
            "distanceKm": route["distance"] / 1000,
            "durationMinutes": round(route["duration"] / 60),
        }
    except (URLError, TimeoutError, KeyError, IndexError, ValueError, TypeError):
        raise HTTPException(503, "Avtomobil yo‘lini hozir aniqlab bo‘lmadi.")


@router.get("/api/driving-route")
def driving_route(startLat: Latitude, startLng: Longitude, endLat: Latitude, endLng: Longitude):
    if (startLat, startLng) == (endLat, endLng):
        raise HTTPException(422, "Ikki xil manzilni tanlang.")
    return fetch_route(f"{startLng:.6f},{startLat:.6f};{endLng:.6f},{endLat:.6f}")
