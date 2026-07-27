"""Проверка геолокации относительно территории Министерства (геозона)."""
from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from app.config import settings


def haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Расстояние между двумя точками в метрах (формула гаверсинуса)."""
    r = 6371000.0  # радиус Земли, м
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * r * asin(sqrt(a))


def is_within_geofence(lat: float, lon: float) -> tuple[bool, int]:
    """Возвращает (в зоне?, расстояние в метрах) относительно офиса."""
    distance = haversine_meters(
        lat, lon, settings.office_latitude, settings.office_longitude
    )
    return distance <= settings.office_radius_meters, int(round(distance))
