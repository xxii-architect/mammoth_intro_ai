"""Weather lookups for MammothOS (contract ``mammoth.weather.v1``) via Open-Meteo.

Stdlib only. No key is needed for the free tier. Open-Meteo's free API is for
non-commercial use, so commercial deployments set ``OPEN_METEO_API_KEY``. That switches
to the customer endpoints, and the key never appears in results or errors.

- ``MAMMOTH_WEATHER_ENABLED`` = ``0`` disables lookups entirely.
- ``MAMMOTH_WEATHER_UNITS`` = ``imperial`` (default) | ``metric``.

Data: Open-Meteo.com, CC BY 4.0. Every result carries the attribution string.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from typing import Any, Callable, Dict, List, Optional

CONTRACT = "mammoth.weather.v1"
ATTRIBUTION = "Weather data by Open-Meteo.com (CC BY 4.0)"
DEFAULT_TIMEOUT = 6.0
CACHE_TTL_SECONDS = 900
CACHE_SIZE = 64
MAX_DAYS = 7
USER_AGENT = "MammothOS/1.0 (+https://command.truexxiisupply.com)"

Transport = Callable[[str, float], Dict[str, Any]]

WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "fog", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "light freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "light freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "light rain showers", 81: "rain showers", 82: "violent rain showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with hail", 99: "thunderstorm with heavy hail",
}
_THUNDER = {95, 96, 99}
_FREEZING = {56, 57, 66, 67, 48}
_SNOW = {71, 73, 75, 77, 85, 86}
_FOG = {45, 48}

# Objective thresholds per unit system: (gust, heat, cold, precip_amount)
_THRESHOLDS = {
    "imperial": {"gust": 35.0, "heat": 95.0, "cold": 20.0, "precip": 0.5},
    "metric": {"gust": 56.0, "heat": 35.0, "cold": -7.0, "precip": 12.0},
}
_UNIT_LABELS = {
    "imperial": {"temp": "°F", "wind": "mph", "precip": "in"},
    "metric": {"temp": "°C", "wind": "km/h", "precip": "mm"},
}


def _env(env: Optional[Dict[str, str]]) -> Dict[str, str]:
    return env if env is not None else os.environ  # type: ignore[return-value]


def weather_enabled(env: Optional[Dict[str, str]] = None) -> bool:
    return str(_env(env).get("MAMMOTH_WEATHER_ENABLED") or "1").strip().lower() not in {"0", "false", "no", "off"}


def describe_code(code: Any) -> str:
    try:
        return WMO_CODES.get(int(code), "unknown conditions")
    except (TypeError, ValueError):
        return "unknown conditions"


def _default_transport(url: str, timeout: float) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310 - fixed Open-Meteo hosts only
        return json.loads(resp.read(1_000_000).decode("utf-8", errors="replace"))


def _num(value: Any) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _at(values: Any, index: int) -> Any:
    return values[index] if isinstance(values, list) and index < len(values) else None


def assess_hazards(days: List[Dict[str, Any]], units: str) -> List[str]:
    """Plain-language hazard flags from fixed thresholds. No model involved."""
    limits = _THRESHOLDS.get(units, _THRESHOLDS["imperial"])
    labels = _UNIT_LABELS.get(units, _UNIT_LABELS["imperial"])
    hazards: List[str] = []
    for day in days:
        when = day.get("date") or "forecast"
        code = day.get("weather_code")
        code = int(code) if isinstance(code, (int, float)) else None
        gust = _num(day.get("wind_gusts_max"))
        high = _num(day.get("temp_max"))
        low = _num(day.get("temp_min"))
        precip = _num(day.get("precipitation_sum"))
        chance = _num(day.get("precipitation_probability_max"))
        uv = _num(day.get("uv_index_max"))
        if code in _THUNDER:
            hazards.append(f"{when}: thunderstorms forecast. Plan to be off exposed ridges and open water.")
        if code in _FREEZING:
            hazards.append(f"{when}: freezing precipitation or fog. Expect icy surfaces.")
        if code in _SNOW:
            hazards.append(f"{when}: snow forecast. Check traction and route conditions.")
        if code in _FOG and code not in _FREEZING:
            hazards.append(f"{when}: fog. Expect low visibility for navigation.")
        if gust is not None and gust >= limits["gust"]:
            hazards.append(f"{when}: wind gusts to {gust:.0f} {labels['wind']}.")
        if high is not None and high >= limits["heat"]:
            hazards.append(f"{when}: heat, high of {high:.0f}{labels['temp']}. Carry extra water.")
        if low is not None and low <= limits["cold"]:
            hazards.append(f"{when}: cold, low of {low:.0f}{labels['temp']}. Plan insulation.")
        if precip is not None and precip >= limits["precip"]:
            hazards.append(f"{when}: heavy precipitation ({precip:g} {labels['precip']}).")
        elif chance is not None and chance >= 70:
            hazards.append(f"{when}: {chance:.0f}% chance of precipitation.")
        if uv is not None and uv >= 8:
            hazards.append(f"{when}: very high UV index ({uv:.0f}).")
    return hazards


class Weather:
    """Cached Open-Meteo client. Thread-safe."""

    def __init__(
        self,
        *,
        env: Optional[Dict[str, str]] = None,
        transport: Optional[Transport] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._env = env
        self._transport = transport or _default_transport
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: "OrderedDict[tuple, tuple[float, Dict[str, Any]]]" = OrderedDict()

    def _key(self) -> str:
        return str(_env(self._env).get("OPEN_METEO_API_KEY") or "").strip()

    def _units(self, units: Optional[str]) -> str:
        value = str(units or _env(self._env).get("MAMMOTH_WEATHER_UNITS") or "imperial").strip().lower()
        return value if value in _THRESHOLDS else "imperial"

    def _url(self, kind: str, params: Dict[str, Any]) -> str:
        key = self._key()
        if kind == "geocode":
            host = "customer-geocoding-api.open-meteo.com" if key else "geocoding-api.open-meteo.com"
            path = "/v1/search"
        else:
            host = "customer-api.open-meteo.com" if key else "api.open-meteo.com"
            path = "/v1/forecast"
        if key:
            params = {**params, "apikey": key}
        return f"https://{host}{path}?{urllib.parse.urlencode(params)}"

    def _fetch(self, kind: str, params: Dict[str, Any], timeout: float) -> Dict[str, Any]:
        cache_key = (kind, tuple(sorted(params.items())))
        now = self._clock()
        with self._lock:
            hit = self._cache.get(cache_key)
            if hit and now - hit[0] < CACHE_TTL_SECONDS:
                self._cache.move_to_end(cache_key)
                return hit[1]
        payload = self._transport(self._url(kind, params), timeout)
        if not isinstance(payload, dict):
            raise ValueError("unexpected payload")
        with self._lock:
            self._cache[cache_key] = (now, payload)
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)
        return payload

    def status(self) -> Dict[str, Any]:
        return {
            "contract": CONTRACT,
            "enabled": weather_enabled(self._env),
            "tier": "commercial" if self._key() else "free_non_commercial",
            "units": self._units(None),
        }

    def geocode(self, place: str, *, timeout: float = DEFAULT_TIMEOUT) -> Optional[Dict[str, Any]]:
        """Resolve ``"Boise"`` or ``"Boise, Idaho"`` to the best-matching place, or ``None``."""
        parts = [p.strip() for p in str(place or "").split(",") if p.strip()]
        if not parts:
            return None
        payload = self._fetch("geocode", {"name": parts[0][:80], "count": 10, "language": "en", "format": "json"}, timeout)
        results = [r for r in payload.get("results") or [] if isinstance(r, dict)]
        if not results:
            return None
        qualifiers = [q.lower() for q in parts[1:]]
        best = results[0]
        if qualifiers:
            for item in results:
                region = " ".join(str(item.get(k) or "") for k in ("admin1", "admin2", "country", "country_code")).lower()
                if all(q in region for q in qualifiers):
                    best = item
                    break
        lat, lon = _num(best.get("latitude")), _num(best.get("longitude"))
        if lat is None or lon is None:
            return None
        label = ", ".join(str(best.get(k)) for k in ("name", "admin1", "country") if best.get(k))
        return {"name": label, "latitude": round(lat, 4), "longitude": round(lon, 4), "timezone": best.get("timezone") or ""}

    def forecast(
        self,
        place: Optional[str] = None,
        *,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        days: int = 3,
        units: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> Dict[str, Any]:
        unit_system = self._units(units)
        base: Dict[str, Any] = {"contract": CONTRACT, "attribution": ATTRIBUTION, "units": unit_system, "query": str(place or "")[:120]}
        if not weather_enabled(self._env):
            return {**base, "status": "disabled", "code": "disabled", "error": "Weather lookups are disabled."}
        try:
            if latitude is not None and longitude is not None:
                lat, lon = float(latitude), float(longitude)
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    return {**base, "status": "error", "code": "bad_coordinates", "error": "Coordinates are out of range."}
                location = {"name": f"{lat:.4f}, {lon:.4f}", "latitude": round(lat, 4), "longitude": round(lon, 4), "timezone": ""}
            else:
                if not str(place or "").strip():
                    return {**base, "status": "error", "code": "empty_location", "error": "A place name or coordinates are required."}
                location = self.geocode(str(place), timeout=timeout)
                if location is None:
                    return {**base, "status": "error", "code": "location_not_found", "error": f"No place found for '{base['query']}'."}
            imperial = unit_system == "imperial"
            params = {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "current": "temperature_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m,wind_gusts_10m",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,uv_index_max,sunrise,sunset",
                "timezone": "auto",
                "forecast_days": max(1, min(int(days or 3), MAX_DAYS)),
            }
            if imperial:
                params.update({"temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "precipitation_unit": "inch"})
            payload = self._fetch("forecast", params, timeout)
        except urllib.error.HTTPError as exc:
            code = "rate_limited" if exc.code == 429 else "provider_error"
            return {**base, "status": "error", "code": code, "error": f"Weather provider returned HTTP {exc.code}."}
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            return {**base, "status": "error", "code": "unreachable", "error": "Weather provider could not be reached."}

        current_raw = payload.get("current") if isinstance(payload.get("current"), dict) else {}
        current = {
            "time": current_raw.get("time"),
            "temperature": _num(current_raw.get("temperature_2m")),
            "feels_like": _num(current_raw.get("apparent_temperature")),
            "precipitation": _num(current_raw.get("precipitation")),
            "wind_speed": _num(current_raw.get("wind_speed_10m")),
            "wind_gusts": _num(current_raw.get("wind_gusts_10m")),
            "weather_code": current_raw.get("weather_code"),
            "conditions": describe_code(current_raw.get("weather_code")),
        } if current_raw else None
        daily = payload.get("daily") if isinstance(payload.get("daily"), dict) else {}
        dates = daily.get("time") if isinstance(daily.get("time"), list) else []
        day_rows = [
            {
                "date": dates[i],
                "weather_code": _at(daily.get("weather_code"), i),
                "conditions": describe_code(_at(daily.get("weather_code"), i)),
                "temp_max": _num(_at(daily.get("temperature_2m_max"), i)),
                "temp_min": _num(_at(daily.get("temperature_2m_min"), i)),
                "precipitation_sum": _num(_at(daily.get("precipitation_sum"), i)),
                "precipitation_probability_max": _num(_at(daily.get("precipitation_probability_max"), i)),
                "wind_speed_max": _num(_at(daily.get("wind_speed_10m_max"), i)),
                "wind_gusts_max": _num(_at(daily.get("wind_gusts_10m_max"), i)),
                "uv_index_max": _num(_at(daily.get("uv_index_max"), i)),
                "sunrise": _at(daily.get("sunrise"), i),
                "sunset": _at(daily.get("sunset"), i),
            }
            for i in range(len(dates))
        ]
        location["timezone"] = location.get("timezone") or payload.get("timezone") or ""
        return {
            **base,
            "status": "ok",
            "location": location,
            "unit_labels": _UNIT_LABELS[unit_system],
            "current": current,
            "daily": day_rows,
            "hazards": assess_hazards(day_rows, unit_system),
        }


def summarize_forecast(result: Dict[str, Any]) -> str:
    """Compact plain-text forecast for prompts and chat output."""
    if result.get("status") != "ok":
        return str(result.get("error") or "Weather unavailable.")
    labels = result.get("unit_labels") or _UNIT_LABELS["imperial"]
    lines = [f"Weather for {result['location']['name']}:"]
    current = result.get("current")
    if current and current.get("temperature") is not None:
        lines.append(
            f"- Now: {current['conditions']}, {current['temperature']:.0f}{labels['temp']}"
            + (f", gusts {current['wind_gusts']:.0f} {labels['wind']}" if current.get("wind_gusts") is not None else "")
        )
    for day in result.get("daily") or []:
        temps = ""
        if day.get("temp_min") is not None and day.get("temp_max") is not None:
            temps = f", {day['temp_min']:.0f}–{day['temp_max']:.0f}{labels['temp']}"
        chance = f", {day['precipitation_probability_max']:.0f}% precip" if day.get("precipitation_probability_max") is not None else ""
        lines.append(f"- {day['date']}: {day['conditions']}{temps}{chance}")
    for hazard in result.get("hazards") or []:
        lines.append(f"- Hazard: {hazard}")
    lines.append(f"({result.get('attribution') or ATTRIBUTION})")
    return "\n".join(lines)


_PLACE_RE = re.compile(
    r"\b(?:in|near|at|around|outside(?:\s+of)?)\s+((?:[A-Z][\w'.-]*)(?:\s+(?:of\s+(?:the\s+)?)?[A-Z][\w'.-]*){0,4}(?:,\s*[A-Z][\w'.-]*(?:\s+[A-Z][\w'.-]*){0,2})?)"
)


_NOT_PLACES = {
    "january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
    "november", "december", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "i", "a", "an", "the", "my", "our", "your", "this", "that", "spring", "summer", "fall", "autumn", "winter",
}


def extract_place(text: str) -> Optional[str]:
    """A capitalized place after in/near/at/around, e.g. "near Stanley, Idaho". Never guesses from common nouns."""
    for match in _PLACE_RE.finditer(str(text or "")):
        place = match.group(1).strip(" .,")
        if place.split()[0].lower().strip(",") not in _NOT_PLACES:
            return place
    return None


_DEFAULT: Optional[Weather] = None
_DEFAULT_LOCK = threading.Lock()


def default_weather() -> Weather:
    global _DEFAULT
    with _DEFAULT_LOCK:
        if _DEFAULT is None:
            _DEFAULT = Weather()
        return _DEFAULT


def weather_forecast(place: Optional[str] = None, **kwargs: Any) -> Dict[str, Any]:
    return default_weather().forecast(place, **kwargs)


def weather_status() -> Dict[str, Any]:
    return default_weather().status()
