from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter
import pycountry

import requests
import time

def get_country_by_city(city_name):
    """
    Определяет страну по названию города через OpenStreetMap Nominatim API.
    """
    base_url = "https://nominatim.openstreetmap.org/search"
    params = {
        "format": "json",
        "q": city_name
    }

    headers = {
        "User-Agent": "Mozilla/5.0"  # Требуется для Nominatim
    }

    try:
        response = requests.get(base_url, params=params, headers=headers)
        data = response.json()

        if data and len(data) > 0:
            country = data[0].get('display_name').split(',')[-1].strip()
            return country if country else None
        else:
            return None

    except:
        return None