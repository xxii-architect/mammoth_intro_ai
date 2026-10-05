import io
import urllib.error

import pytest

from mammoth_os import weather as wx
from mammoth_os.agents.field_ops_agent import FieldOpsAgent

GEO = {
    "results": [
        {"name": "Boise", "latitude": 43.6135, "longitude": -116.2035, "admin1": "Idaho", "country": "United States", "country_code": "US", "timezone": "America/Boise"},
        {"name": "Boise City", "latitude": 36.7295, "longitude": -102.5132, "admin1": "Oklahoma", "country": "United States", "country_code": "US"},
    ]
}
STANLEY = {"results": [
    {"name": "Stanley", "latitude": 54.87, "longitude": -1.69, "admin1": "England", "country": "United Kingdom"},
    {"name": "Stanley", "latitude": 44.2163, "longitude": -114.9381, "admin1": "Idaho", "country": "United States"},
]}
FORECAST = {
    "timezone": "America/Boise",
    "current": {"time": "2025-06-01T10:00", "temperature_2m": 71.2, "apparent_temperature": 70.0, "precipitation": 0.0, "weather_code": 2, "wind_speed_10m": 8.0, "wind_gusts_10m": 15.0},
    "daily": {
        "time": ["2025-06-01", "2025-06-02"],
        "weather_code": [2, 95],
        "temperature_2m_max": [88.0, 97.0],
        "temperature_2m_min": [55.0, 60.0],
        "precipitation_sum": [0.0, 0.7],
        "precipitation_probability_max": [10, 80],
        "wind_speed_10m_max": [12.0, 25.0],
        "wind_gusts_10m_max": [20.0, 45.0],
        "uv_index_max": [7.0, 9.0],
        "sunrise": ["2025-06-01T06:00", "2025-06-02T06:00"],
        "sunset": ["2025-06-01T21:00", "2025-06-02T21:00"],
    },
}


class FakeTransport:
    def __init__(self, geo=GEO, forecast=FORECAST, error=None):
        self.geo, self.forecast, self.error = geo, forecast, error
        self.urls = []

    def __call__(self, url, timeout):
        self.urls.append(url)
        if self.error is not None:
            raise self.error
        return self.geo if "/v1/search" in url else self.forecast


def _client(env=None, transport=None, clock=None):
    times = clock or [0.0]
    return wx.Weather(env=env or {}, transport=transport or FakeTransport(), clock=lambda: times[0])


def test_forecast_parses_and_flags_hazards():
    transport = FakeTransport()
    result = _client(transport=transport).forecast("Boise, Idaho")
    assert result["status"] == "ok" and result["contract"] == wx.CONTRACT
    assert result["attribution"] == wx.ATTRIBUTION
    assert result["location"]["name"] == "Boise, Idaho, United States"
    assert result["current"]["conditions"] == "partly cloudy"
    assert [d["conditions"] for d in result["daily"]] == ["partly cloudy", "thunderstorm"]
    hazards = " ".join(result["hazards"])
    assert "thunderstorms" in hazards and "gusts to 45 mph" in hazards and "heat" in hazards
    assert "heavy precipitation" in hazards and "UV" in hazards
    assert not any(h.startswith("2025-06-01") for h in result["hazards"])
    forecast_url = transport.urls[1]
    assert forecast_url.startswith("https://api.open-meteo.com/v1/forecast?") and "temperature_unit=fahrenheit" in forecast_url


def test_geocode_uses_qualifier_to_pick_region():
    client = _client(transport=FakeTransport(geo=STANLEY))
    assert client.geocode("Stanley, Idaho")["latitude"] == 44.2163
    assert client.geocode("Stanley")["latitude"] == 54.87


def test_metric_units_skip_imperial_params():
    transport = FakeTransport()
    result = _client({"MAMMOTH_WEATHER_UNITS": "metric"}, transport).forecast(latitude=43.6, longitude=-116.2)
    assert result["status"] == "ok" and result["units"] == "metric"
    assert "temperature_unit" not in transport.urls[0] and len(transport.urls) == 1


def test_commercial_key_switches_hosts_and_never_leaks():
    transport = FakeTransport()
    client = _client({"OPEN_METEO_API_KEY": "om-secret"}, transport)
    result = client.forecast("Boise")
    assert transport.urls[0].startswith("https://customer-geocoding-api.open-meteo.com/")
    assert transport.urls[1].startswith("https://customer-api.open-meteo.com/") and "apikey=om-secret" in transport.urls[1]
    assert "om-secret" not in repr(result)
    assert client.status()["tier"] == "commercial"


def test_cache_avoids_repeat_calls():
    clock = [0.0]
    transport = FakeTransport()
    client = _client(transport=transport, clock=clock)
    client.forecast("Boise")
    client.forecast("Boise")
    assert len(transport.urls) == 2
    clock[0] += wx.CACHE_TTL_SECONDS + 1
    client.forecast("Boise")
    assert len(transport.urls) == 4


@pytest.mark.parametrize("kwargs,code", [
    ({"place": ""}, "empty_location"),
    ({"latitude": 120.0, "longitude": 0.0}, "bad_coordinates"),
])
def test_input_errors(kwargs, code):
    place = kwargs.pop("place", None)
    assert _client().forecast(place, **kwargs)["code"] == code


def test_location_not_found_and_provider_errors():
    assert _client(transport=FakeTransport(geo={"results": []})).forecast("Nowhere")["code"] == "location_not_found"
    err = urllib.error.HTTPError("https://api.open-meteo.com", 429, "slow", {}, io.BytesIO(b""))
    assert _client(transport=FakeTransport(error=err)).forecast("Boise")["code"] == "rate_limited"
    assert _client(transport=FakeTransport(error=urllib.error.URLError("down"))).forecast("Boise")["code"] == "unreachable"


def test_disabled():
    transport = FakeTransport()
    result = _client({"MAMMOTH_WEATHER_ENABLED": "0"}, transport).forecast("Boise")
    assert result["status"] == "disabled" and transport.urls == []


@pytest.mark.parametrize("text,expected", [
    ("Plan a hard navigation day near Stanley, Idaho this weekend", "Stanley, Idaho"),
    ("camping trip in the Sawtooth Mountains", None),
    ("backpacking in Sawtooth Wilderness", "Sawtooth Wilderness"),
    ("trip in May at Craters of the Moon", "Craters of the Moon"),
    ("medium firecraft in desert conditions", None),
    ("rollout on Monday", None),
])
def test_extract_place_is_conservative(text, expected):
    assert wx.extract_place(text) == expected


def test_summarize_forecast_includes_attribution():
    text = wx.summarize_forecast(_client().forecast("Boise"))
    assert text.startswith("Weather for Boise") and "Hazard:" in text and "Open-Meteo" in text


class _StubLLM:
    def __init__(self):
        self.prompts = []

    async def generate(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return '{"situation_summary": "ok", "priorities": []}'


def _patch_field_ops(monkeypatch, weather_client):
    import mammoth_os.llm_client as llm_client

    llm = _StubLLM()
    monkeypatch.setattr(llm_client, "get_llm_client", lambda: llm)
    monkeypatch.setattr(wx, "default_weather", lambda: weather_client)
    return llm


def test_field_ops_adds_live_weather_for_named_place(monkeypatch):
    llm = _patch_field_ops(monkeypatch, _client())
    result = FieldOpsAgent(user_id="wx-1").run({"prompt": "Navigation drill", "location": "Boise, Idaho", "difficulty": "easy"})
    assert result["status"] == "ok"
    assert result["weather"]["status"] == "ok" and "live_weather" in result["quality_flags"]
    assert result["risk_level"] == "high"
    assert any(note.startswith("Weather hazard:") for note in result["safety_notes"])
    assert "Live forecast" in llm.prompts[0] and "Open-Meteo" in llm.prompts[0]
    assert result["forecast"][0].startswith("Weather for Boise") and not any("Hazard" in line for line in result["forecast"])


def test_field_ops_skips_weather_without_place(monkeypatch):
    transport = FakeTransport()
    llm = _patch_field_ops(monkeypatch, _client(transport=transport))
    result = FieldOpsAgent(user_id="wx-2").run("medium firecraft in desert conditions")
    assert result["weather"] is None and result["forecast"] == [] and transport.urls == []
    assert "live_weather" not in result["quality_flags"] and "Live forecast" not in llm.prompts[0]


def test_field_ops_reports_weather_failure_without_failing(monkeypatch):
    _patch_field_ops(monkeypatch, _client(transport=FakeTransport(error=urllib.error.URLError("down"))))
    result = FieldOpsAgent(user_id="wx-3").run({"prompt": "Ridge hike", "location": "Boise"})
    assert result["status"] == "ok"
    assert result["weather"]["code"] == "unreachable" and "weather_unavailable" in result["quality_flags"]
    assert "unreachable" not in result["summary"]


def test_agent_loop_registers_weather_tool(monkeypatch):
    import api_server

    ctx = api_server._agent_tool_context(None)[0]
    registry, _ = api_server._build_agent_tool_registry()
    assert "weather_forecast" in {t["name"] for t in registry.catalog(ctx)}
    monkeypatch.setenv("MAMMOTH_WEATHER_ENABLED", "0")
    registry, _ = api_server._build_agent_tool_registry()
    assert "weather_forecast" not in {t["name"] for t in registry.catalog(ctx)}
